import unittest
from tools.dev.usb_guest_library import allowed_request


class GuestUsbScopeTest(unittest.TestCase):
    def test_only_library_and_guest_routes_are_reachable(self):
        for method,path in [('GET','/health'),('POST','/api/v3/auth/guest'),('GET','/api/v3/me/music-assets'),('PUT','/api/v3/favorites'),('POST','/api/v3/music/assets/test/playback-events'),('POST','/api/v3/feedback-records'),('POST','/api/v3/me/feedback-evidence/clear')]:
            self.assertTrue(allowed_request(method,path),(method,path))
        for method,path in [('POST','/api/v3/music/generate'),('POST','/api/v3/auth/login'),('POST','/api/v3/documents'),('GET','/api/v3/music/assets/../secret'),('GET','/api/v3/feedback-records/a/b'),('POST','/api/v3/me/music-assets')]:
            self.assertFalse(allowed_request(method,path),(method,path))
