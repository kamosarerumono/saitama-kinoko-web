import ctypes as c
import io, unittest
from unittest.mock import Mock, patch
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import windows_credential as m

class Tests(unittest.TestCase):
    def setUp(self):
        self.tty = patch.object(m.sys.stdin, 'isatty', return_value=True); self.tty.start(); self.addCleanup(self.tty.stop)
        self.output = io.StringIO(); self.prints = patch('sys.stdout', self.output); self.prints.start(); self.addCleanup(self.prints.stop)
        self.factory = Mock(); self.store = self.factory.return_value
        # Test values are synthetic and never sent to an OS credential API.
    def test_registered_no_prompt(self):
        self.store.read.return_value = 'synthetic'
        with patch.object(m, 'hidden') as hidden:
            self.assertEqual(m.password_for_publish(self.factory), 'synthetic'); hidden.assert_not_called()
    def test_missing_prompts_without_saving(self):
        self.store.read.side_effect = m.MissingCredential()
        with patch.object(m, 'hidden', return_value='synthetic'):
            self.assertEqual(m.password_for_publish(self.factory), 'synthetic')
        self.store.write.assert_not_called()
    def test_denied_never_falls_back(self):
        self.store.read.side_effect = m.CredentialError()
        with patch.object(m, 'hidden') as hidden:
            self.assertRaises(m.CredentialError, m.password_for_publish, self.factory); hidden.assert_not_called()
    def test_registration_no_read_or_network(self):
        with patch('builtins.input', return_value='REGISTER'), patch.object(m, 'hidden', side_effect=['synthetic', 'synthetic']):
            self.assertEqual(m.manage('register', self.factory), 0)
        self.store.write.assert_called_once_with('synthetic'); self.store.read.assert_not_called()
        self.assertNotIn('synthetic', self.output.getvalue())
    def test_mismatch_no_write(self):
        with patch('builtins.input', return_value='REGISTER'), patch.object(m, 'hidden', side_effect=['one', 'two']):
            self.assertRaises(m.CredentialError, m.manage, 'register', self.factory)
        self.store.write.assert_not_called()
    def test_cancel_no_store_access(self):
        with patch('builtins.input', return_value='NO'): m.manage('register', self.factory)
        self.factory.assert_not_called()
    def test_delete_only(self):
        with patch('builtins.input', return_value='DELETE'): m.manage('delete', self.factory)
        self.store.delete.assert_called_once(); self.store.read.assert_not_called(); self.store.write.assert_not_called()
    def test_noninteractive_no_store_access(self):
        with patch.object(m.sys.stdin, 'isatty', return_value=False):
            self.assertRaises(m.CredentialError, m.manage, 'register', self.factory)
            self.assertRaises(m.CredentialError, m.password_for_publish, self.factory)
        self.factory.assert_not_called()
    def test_no_echo_fallback(self):
        def warn(_):
            import warnings
            warnings.warn('test', m.getpass.GetPassWarning)
        with patch.object(m.getpass, 'getpass', side_effect=warn): self.assertRaises(m.getpass.GetPassWarning, m.hidden, 'test')
    def test_native_write_fixed_scope(self):
        store = object.__new__(m.NativeStore); store.api = Mock(); held = []
        def write(ptr, flags):
            item = c.cast(ptr, c.POINTER(m.Credential)).contents
            self.assertEqual((item.Type, item.Persist, item.TargetName, item.UserName, flags), (1, 2, m.TARGET, 'ippon', 0))
            held.append(item.CredentialBlob)
            self.assertEqual(c.string_at(item.CredentialBlob, item.CredentialBlobSize), 'synthetic'.encode('utf-16-le'))
            return True
        store.api.CredWriteW.side_effect = write
        store.write('synthetic')
        # Pointer lifetime ends on return; inspect wiping separately through source review.
        store.api.CredReadW.assert_not_called()
    def test_native_read_metadata_and_free(self):
        store = object.__new__(m.NativeStore); store.api = Mock()
        blob = (c.c_ubyte * 18).from_buffer_copy('synthetic'.encode('utf-16-le'))
        item = m.Credential(); item.Type=1; item.Persist=2; item.TargetName=m.TARGET; item.UserName='ippon'; item.CredentialBlob=blob; item.CredentialBlobSize=18
        def read(target, kind, flags, out):
            self.assertEqual((target,kind,flags),(m.TARGET,1,0))
            c.cast(out,c.POINTER(c.POINTER(m.Credential)))[0]=c.pointer(item); return True
        store.api.CredReadW.side_effect=read
        self.assertEqual(store.read(),'synthetic'); self.assertEqual(bytes(blob),bytes(18)); store.api.CredFree.assert_called_once()
        item.UserName='different'
        self.assertRaises(m.CredentialError,store.read)
        self.assertEqual(store.api.CredFree.call_count,2)

if __name__ == '__main__': unittest.main(verbosity=2)
