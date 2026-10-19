"""Fixed Windows credential target; import performs no native API calls."""
import ctypes as c
from ctypes import wintypes as w
import getpass, sys, warnings
TARGET = 'GT030:FTPS:ippon.sakura.ne.jp:ippon'
USER = 'ippon'
class CredentialError(RuntimeError): pass
class MissingCredential(CredentialError): pass
class Credential(c.Structure):
    _fields_ = [('Flags', w.DWORD), ('Type', w.DWORD), ('TargetName', w.LPWSTR),
                ('Comment', w.LPWSTR), ('LastWritten', w.FILETIME),
                ('CredentialBlobSize', w.DWORD), ('CredentialBlob', c.POINTER(c.c_ubyte)),
                ('Persist', w.DWORD), ('AttributeCount', w.DWORD), ('Attributes', c.c_void_p),
                ('TargetAlias', w.LPWSTR), ('UserName', w.LPWSTR)]
class NativeStore:
    def __init__(self):
        if sys.platform != 'win32': raise CredentialError('Windows is required')
        self.api = c.WinDLL('advapi32', use_last_error=True)
        kernel = c.WinDLL('kernel32', use_last_error=True)
        for api, name, expected in [(self.api, 'GetUserNameW', 'kamos'), (kernel, 'GetComputerNameW', 'AYUMI-D')]:
            fn = getattr(api, name); fn.argtypes = [w.LPWSTR, c.POINTER(w.DWORD)]; fn.restype = w.BOOL
            buf = c.create_unicode_buffer(256); size = w.DWORD(256)
            if not fn(buf, c.byref(size)) or buf.value.casefold() != expected.casefold():
                raise CredentialError('Use AYUMI-D as kamos')
        self.api.CredReadW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, c.POINTER(c.POINTER(Credential))]
        self.api.CredReadW.restype = w.BOOL
        self.api.CredWriteW.argtypes = [c.POINTER(Credential), w.DWORD]; self.api.CredWriteW.restype = w.BOOL
        self.api.CredDeleteW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD]; self.api.CredDeleteW.restype = w.BOOL
        self.api.CredFree.argtypes = [c.c_void_p]; self.api.CredFree.restype = None
    def read(self):
        ptr = c.POINTER(Credential)()
        if not self.api.CredReadW(TARGET, 1, 0, c.byref(ptr)):
            if c.get_last_error() == 1168: raise MissingCredential('Not registered')
            raise CredentialError('Windows credential read failed')
        try:
            item = ptr.contents
            if item.Type != 1 or item.Persist != 2 or item.UserName != USER or item.TargetName != TARGET:
                raise CredentialError('Credential metadata does not match')
            if not item.CredentialBlobSize or item.CredentialBlobSize > 2560 or item.CredentialBlobSize % 2:
                raise CredentialError('Invalid credential size')
            return c.string_at(item.CredentialBlob, item.CredentialBlobSize).decode('utf-16-le')
        finally:
            if ptr.contents.CredentialBlob and ptr.contents.CredentialBlobSize <= 2560:
                c.memset(ptr.contents.CredentialBlob, 0, ptr.contents.CredentialBlobSize)
            self.api.CredFree(ptr)
    def write(self, password):
        blob = bytearray(password.encode('utf-16-le'))
        try:
            if not blob or len(blob) > 2560: raise CredentialError('Unsupported password length')
            buffer = (c.c_ubyte * len(blob)).from_buffer(blob)
            item = Credential(); item.Type = 1; item.TargetName = TARGET; item.UserName = USER
            item.Persist = 2; item.CredentialBlobSize = len(blob); item.CredentialBlob = buffer
            if not self.api.CredWriteW(c.byref(item), 0): raise CredentialError('Registration failed')
        finally:
            for i in range(len(blob)): blob[i] = 0
    def delete(self):
        if not self.api.CredDeleteW(TARGET, 1, 0) and c.get_last_error() != 1168:
            raise CredentialError('Deletion failed')
def hidden(prompt):
    if not sys.stdin.isatty(): raise CredentialError('Use your interactive Windows terminal')
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        return getpass.getpass(prompt)
def password_for_publish(store_factory=NativeStore):
    if not sys.stdin.isatty(): raise CredentialError('Use your interactive Windows terminal')
    try: return store_factory().read()
    except MissingCredential:
        print('Not registered. Run REGISTER_FTPS.cmd to save, or enter once below (not saved).')
        return hidden('Existing Sakura server password (not saved): ')
def manage(action, store_factory=NativeStore):
    if action not in ('register', 'delete'): raise CredentialError('Choose register or delete')
    if not sys.stdin.isatty(): raise CredentialError('Use your interactive Windows terminal')
    print('AYUMI-D / kamos: ' + TARGET)
    print('Local Windows credential. Other processes running as this user may read it. No upload.')
    print('REGISTER replaces this one saved entry if it already exists.')
    if input('Type ' + action.upper() + ' to continue: ') != action.upper():
        print('Cancelled; no changes.'); return 0
    store = store_factory()
    if action == 'delete':
        store.delete(); print('Removed or already absent. Publishing returns to hidden input.'); return 0
    password = confirmation = None
    try:
        password = hidden('Sakura password to save (hidden): ')
        confirmation = hidden('Repeat password (hidden): ')
        if not password or password != confirmation: raise CredentialError('Empty or mismatched input; not saved')
        store.write(password)
        print('Saved for this PC only. No authentication or upload was performed.')
    finally: del password, confirmation
    return 0
if __name__ == '__main__':
    try:
        if len(sys.argv) != 2: raise CredentialError('Choose register or delete; no password argument')
        raise SystemExit(manage(sys.argv[1]))
    except (Exception, KeyboardInterrupt):
        print('Stopped. No secret details printed. Check input and Windows account.'); raise SystemExit(2)
