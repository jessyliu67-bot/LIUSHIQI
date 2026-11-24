"""Small, authenticated-only DeepSeek connectivity diagnostics.
No user/company document content is ever included in the test payload.
Do not report a mere configured key as a successful connection.
"""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import os
import time
import threading
from typing import Any
import httpx

ENDPOINT = 'https://api.deepseek.com/chat/completions'
_LOCK = threading.Lock()
_LAST: dict[str, Any] | None = None
_LAST_KEY_HASH: str | None = None
_LAST_MODEL: str | None = None
_IN_PROGRESS = False


def get_model() -> str:
    return os.environ.get('DEEPSEEK_MODEL', 'deepseek-flash').strip() or 'deepseek-flash'


def _key() -> str:
    return os.environ.get('DEEPSEEK_API_KEY', '').strip()


def _fingerprint(key: str) -> str:
    return hashlib.sha256(key.encode('utf-8')).hexdigest() if key else ''


def status() -> dict[str, Any]:
    key, model = _key(), get_model()
    with _LOCK:
        prior = dict(_LAST) if _LAST and _LAST_KEY_HASH == _fingerprint(key) and _LAST_MODEL == model else None
        running = _IN_PROGRESS
    return {
        'configured': bool(key),
        'model': model,
        'endpoint': ENDPOINT,
        'tested': bool(prior),
        'last_test': prior,
        'in_progress': running,
    }


def _classify_http(status_code: int) -> tuple[str, str]:
    if status_code == 401:
        return 'invalid_key', 'API Key 不正确或已失效，请在 .env 中更新后重启程序。'
    if status_code == 403:
        return 'forbidden', '已连接到 DeepSeek，但当前账号没有调用权限。'
    if status_code == 402:
        return 'billing', 'DeepSeek 账号余额或计费状态异常，请检查账号。'
    if status_code == 429:
        return 'rate_limited', '调用受到限流或配额限制，请稍后重试并检查账号限制。'
    if status_code == 400:
        return 'bad_request', 'DeepSeek 拒绝了测试请求，请检查模型名与 API 参数。'
    if status_code == 404:
        return 'model_unavailable', '接口或模型不存在，请检查当前模型配置。'
    if status_code >= 500:
        return 'provider_error', 'DeepSeek 服务暂时异常，请稍后重试。'
    return 'http_error', f'DeepSeek 返回 HTTP {status_code}，连接未通过。'


def _probe(http_client=None) -> dict[str, Any]:
    """Perform one actual model generation. Inject a fake http client in tests."""
    key, model = _key(), get_model()
    start = time.monotonic()
    result: dict[str, Any] = {'ok': False, 'state': 'error', 'model': model, 'http_status': None,
                              'latency_ms': None, 'message': '', 'reply': None, 'usage': None,
                              'tested_at': datetime.now(timezone.utc).isoformat(timespec='seconds')}
    if not key:
        result.update(state='missing_key', message='未配置 DeepSeek API Key。请在项目 .env 中填写 DEEPSEEK_API_KEY 并重启。')
        return result
    if model not in ('deepseek-flash', 'deepseek-v4-pro'):
        result.update(state='invalid_model', message='模型配置无效，请使用 deepseek-flash 或 deepseek-v4-pro。')
        return result

    # Never send site/company/private documents for the connectivity test.
    data = {
        'model': model, 'thinking': {'type': 'disabled'}, 'max_tokens': 64,
        'messages': [{'role': 'user', 'content': 'Connection check. Reply with exactly BIG_BANG_OK and nothing else.'}],
        'stream': False
    }
    client = http_client or httpx.Client(timeout=httpx.Timeout(25.0, connect=7.0), trust_env=False)
    try:
        response = client.post(ENDPOINT, headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'}, json=data)
        result['http_status'] = response.status_code
        if response.status_code != 200:
            result['state'], result['message'] = _classify_http(response.status_code)
            return result
        try:
            payload = response.json()
            content = payload.get('choices', [{}])[0].get('message', {}).get('content', '')
            reply = str(content or '').strip()
            usage = payload.get('usage') or {}
        except (ValueError, TypeError, KeyError, IndexError, AttributeError):
            result.update(state='invalid_response', message='接口返回成功状态码，但响应格式无法解析。')
            return result
        result['reply'] = reply[:120]  # only fixed non-private probe text
        result['usage'] = {k: usage.get(k) for k in ('prompt_tokens', 'completion_tokens', 'total_tokens') if isinstance(usage.get(k), int)}
        if reply == 'BIG_BANG_OK':
            result.update(ok=True, state='connected', message='验证通过：DeepSeek 已收到请求并正确返回测试内容，可以调用该模型。')
        else:
            result.update(state='unexpected_reply', message='请求已到达 DeepSeek，但模型返回内容与预期不一致，请重试。')
        return result
    except httpx.TimeoutException:
        result.update(state='timeout', message='连接 DeepSeek 超时。请检查网络、代理或防火墙后重试。')
    except httpx.ConnectError:
        result.update(state='network_error', message='无法连接 DeepSeek。请检查网络或 DNS，并确认本机可以访问 api.deepseek.com。')
    except httpx.HTTPError:
        result.update(state='network_error', message='DeepSeek 网络请求失败，请检查本机网络或代理配置。')
    except Exception:
        result.update(state='unexpected_error', message='测试过程中出现异常，详情请查看本地应用日志。')
    finally:
        result['latency_ms'] = round((time.monotonic() - start) * 1000)
        if http_client is None:
            client.close()
    return result


def run_test(http_client=None) -> dict[str, Any]:
    global _LAST, _LAST_KEY_HASH, _LAST_MODEL, _IN_PROGRESS
    with _LOCK:
        if _IN_PROGRESS:
            return {'ok': False, 'state':'already_running', 'message':'已有一个连接测试正在进行，请稍后查看结果。', 'model':get_model()}
        _IN_PROGRESS = True
    try:
        result = _probe(http_client)
        # This is non-sensitive connection metadata, deliberately kept in process memory only.
        with _LOCK:
            _LAST, _LAST_KEY_HASH, _LAST_MODEL = dict(result), _fingerprint(_key()), get_model()
        return result
    finally:
        with _LOCK:
            _IN_PROGRESS = False
