import ssl
import unittest
from unittest.mock import Mock, patch
import providers

class HTTPSContextTests(unittest.TestCase):
    def test_source_verifies_certificates_and_hostname(self):
        with patch('providers.sys.frozen',False,create=True):
            context=providers.verified_http_context()
        self.assertEqual(context.verify_mode,ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)

    def test_frozen_mac_adds_only_os_roots(self):
        context=Mock()
        with patch('providers.ssl.create_default_context',return_value=context), patch('providers.sys.platform','darwin'), patch('providers.sys.frozen',True,create=True), patch('providers.Path.is_file',return_value=True):
            self.assertIs(providers.verified_http_context(),context)
        context.load_verify_locations.assert_called_once_with(cafile=str(providers.Path('/etc/ssl/cert.pem')))

    def test_missing_roots_and_other_platforms_keep_default_trust(self):
        for platform,frozen,present in [('darwin',True,False),('win32',True,True),('darwin',False,True)]:
            context=Mock()
            with patch('providers.ssl.create_default_context',return_value=context), patch('providers.sys.platform',platform), patch('providers.sys.frozen',frozen,create=True), patch('providers.Path.is_file',return_value=present):
                self.assertIs(providers.verified_http_context(),context)
            context.load_verify_locations.assert_not_called()

    def test_invalid_os_roots_fail_closed(self):
        context=Mock();context.load_verify_locations.side_effect=ssl.SSLError('invalid fixture root')
        with patch('providers.ssl.create_default_context',return_value=context), patch('providers.sys.platform','darwin'), patch('providers.sys.frozen',True,create=True), patch('providers.Path.is_file',return_value=True):
            with self.assertRaises(ssl.SSLError):providers.verified_http_context()
