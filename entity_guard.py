"""Source-aware entity preflight for BIG BANG V5.3.

Not a corporate registry verification or legal opinion. Values cannot be invented.
"""
from __future__ import annotations
import re
from typing import Mapping

CJK = re.compile(r'[\u3400-\u9fff]')
NON_NAME = re.compile(r'^(?:LEGAL COMPANY NAME|COMPANY NAME|NAME|N/?A|NONE|UNKNOWN|TEST|DEMO)$',re.I)
COMPANY_SUFFIX = re.compile(r'\b(?:Co\.?\s*,?\s*Ltd\.?|Ltd\.?|Limited|LLC|L\.L\.C\.|Inc\.?|Incorporated|Corporation|Corp\.?|GmbH|Pte\.?\s*Ltd\.?|S\.A\.|B\.V\.)\b',re.I)
TOKEN = re.compile(r'\[\[[A-Z][A-Z_]+\]\]|REPLACE_WITH_[A-Z_]+')


def phone_issue(value:str)->str:
    """Reject malformed international numbers; in particular +1 needs 10 NANP digits."""
    p=str(value or '').strip()
    # Common supplier/source format: (+1) 6193241351 (same digits as +1 6193241351).
    p=re.sub(r'^\(\s*\+([1-9]\d{0,2})\s*\)',r'+\1',p)
    if not p:
        return '缺少主体通用客服电话：请填写真实电话号码（同一主体下全部店铺共用）'
    if not re.fullmatch(r'\+?[0-9()\-\s.]+',p):
        return '主体通用电话含非数字字符或不支持的格式，请检查'
    number=''.join(re.findall(r'\d',p))
    if p.startswith('+1') and len(number)!=11:
        return f'主体通用电话 {p} 格式错误：+1 后必须有10位数字，目前有{len(number)-1}位'
    if p.startswith('1') and not p.startswith('+') and len(number)==11:
        return '以国家代码1开头的国际电话请使用 +1 格式'
    if p.startswith('+') and not 8<=len(number)<=15:
        return '国际电话必须包含国家代码，且总数字位数一般为8至15位'
    if not p.startswith('+') and not 7<=len(number)<=15:
        return '电话位数不合理，请填写包含国家代码的真实客服电话'
    if len(set(number))==1:
        return '电话疑似无效测试号码，请提供实际客服号码'
    return ''


def entity_issues(fields:Mapping,strict_english=True)->list[str]:
    name=str(fields.get('name') or '').strip()
    address=str(fields.get('address') or '').strip()
    errors=[]
    if not name or len(name)<3 or NON_NAME.match(name):
        errors.append('未识别到有效的公司法定名称，请依据营业执照和公司文件填写')
    elif strict_english and CJK.search(name):
        errors.append('公司名称仍含中文或可能是个人姓名。请提供该公司的真实英文展示名称，不能把法定代表人当作企业')
    elif not COMPANY_SUFFIX.search(name):
        errors.append('公司名称未包含可识别的公司组织形式，请核对是否误填法定代表人或品牌名称')
    if not address:
        errors.append('缺少公司注册地址，不能使用法定代表人的个人地址代替')
    elif strict_english and CJK.search(address):
        errors.append('注册地址仍包含中文；英文店铺交付包需要经过核对的英文地址')
    phone=phone_issue(str(fields.get('phone') or ''))
    if phone:errors.append(phone)
    return errors


def english_source_fields(text:str)->dict[str,str]:
    """Read company metadata in a TXT/DOCX, including value on the next line.

    File names and director / individual fields never become the legal entity name.
    Values derived here remain operator-supplied, NOT registry-verified.
    """
    original=[x.strip().strip('*').strip() for x in text.splitlines()]
    lines=[x for x in original if x]
    source={}
    aliases={
      'businesslicenseentity':'name','legalcompanyname':'name',
      'legalbusinessname':'name','operatedby':'name','companyname':'name',
      'registeredaddress':'address','registeredbusinessaddress':'address',
      'registeredofficeaddress':'address',
      'customerservice':'phone','customerservicephone':'phone',
      'supportphone':'phone','customerphone':'phone','phone':'phone','telephone':'phone',
      'registrationnumber':'registration_no','unifiedsocialcreditcode':'registration_no',
      'companyregistrationnumber':'registration_no','ein':'registration_no',
      'email':'email','companyemail':'email','officialemail':'email',
      'country':'country','countryofincorporation':'country'
    }
    for index,line in enumerate(lines):
        m=re.match(r'^([^:：]{2,75})\s*[:：]\s*(.*)$',line)
        if not m:continue
        key=re.sub(r'[^a-z]','',m.group(1).casefold())
        field=aliases.get(key)
        if not field:continue
        value=m.group(2).strip(' *\t')
        if not value and index+1<len(lines):
            next_line=lines[index+1].strip()
            if not re.match(r'^[^:：]{2,75}\s*[:：]',next_line):value=next_line
        if not value:continue
        if field=='email':
            if not re.fullmatch(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}',value) or CJK.search(value):continue
        if field=='name' and (re.search(r'法定代表人|法人姓名|身份证',value) or len(value)>200):continue
        source.setdefault(field,value[:500])
    if source.get('address') and re.search(r'\bChina\b|\bGuangzhou\b|\bZhijiang\b',source['address'],re.I):
        source.setdefault('country','China')
    return source


def chinese_credit_code_valid(code:str)->bool:
    """Validate 18-character Unified Social Credit Code checksum (GB 32100)."""
    alphabet='0123456789ABCDEFGHJKLMNPQRTUWXY'
    weights=(1,3,9,27,19,26,16,17,20,29,25,13,8,24,10,30,28)
    text=str(code or '').strip().upper()
    if len(text)!=18 or any(c not in alphabet for c in text):return False
    check=(31-sum(alphabet.index(c)*w for c,w in zip(text[:17],weights))%31)%31
    return alphabet[check]==text[-1]
