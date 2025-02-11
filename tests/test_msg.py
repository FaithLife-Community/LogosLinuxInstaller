import unittest

import logging
import ou_dedetai.msg as msg


class TestMsg(unittest.TestCase):
    def test_update_log_level(self):
        new_level = logging.DEBUG
        level = None
        msg.update_log_level(new_level)
        for h in logging.getLogger().handlers:
            if isinstance(h, logging.StreamHandler):
                level = h.level
        self.assertEqual(level, new_level)
