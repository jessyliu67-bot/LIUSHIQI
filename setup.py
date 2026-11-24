"""One-time local setup for BIG BANG V35."""
from pathlib import Path
import secrets
ROOT = Path(__file__).resolve().parent
p = ROOT / '.env'
if p.exists():
    print('Environment already configured; .env was not changed.')
else:
    password = secrets.token_urlsafe(14)
    p.write_text('ADMIN_PASSWORD='+password+'\nSESSION_SECRET='+secrets.token_urlsafe(48)+'\nDEEPSEEK_API_KEY=\nDEEPSEEK_MODEL=deepseek-flash\n', encoding='utf-8')
    print('\n========== BIG BANG V35 LOCAL LOGIN ==========')
    print('User: admin')
    print('Password:', password)
    print('Saved in .env; keep this file private.')
    print('=============================================\n')
