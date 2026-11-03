#!/usr/bin/env python3
"""Tests of build_list.py: python3 tools/test_build_list.py"""
import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_list as b  # noqa: E402

DAY = datetime.date(2026, 11, 3)


def lobby(*rooms):
    return {'rooms': [dict({'netVersion': 4, 'hasPassword': False, 'port': 24872, 'name': 'Room'}, **r) for r in rooms]}


class Names(unittest.TestCase):
    def test_colon_link_and_spaces(self):
        self.assertEqual(b.clean_name('Animal Crossing: New Leaf'), 'Animal Crossing - New Leaf')
        self.assertEqual(b.clean_name('MH4U   https://discord.gg/abc  EU'), 'MH4U EU')
        self.assertEqual(b.clean_name('Tempest Discord bit.ly/3tWcC3m'), 'Tempest Discord')
        self.assertEqual(b.clean_name('Room discord.gg/xyz #2'), 'Room #2')
        self.assertEqual(b.clean_name('Ver. 1.2 room'), 'Ver. 1.2 room')
        self.assertEqual(b.clean_name('a\tb\nc'), 'a b c')
        self.assertEqual(len(b.clean_name('x' * 100)), 64)

    def test_hosts(self):
        self.assertTrue(b.valid_host('88.198.47.46'))
        self.assertTrue(b.valid_host('rooms.example.org'))
        for host in ('192.168.1.2', '10.0.0.1', '127.0.0.1', '0.0.0.0', '::1', 'box.local', 'a b', '999.1.1.1', ''):
            self.assertFalse(b.valid_host(host), host)


class Lines(unittest.TestCase):
    def test_secret_keeps_its_colons(self):
        self.assertEqual(b.parse_line('1.2.3.4:5000:Room:a:b:c', 'x'), ('1.2.3.4', 5000, 'Room', 'a:b:c'))
        self.assertEqual(b.parse_line('1.2.3.4:5000:Room', 'x'), ('1.2.3.4', 5000, 'Room', ''))
        self.assertIsNone(b.parse_line('# comment', 'x'))
        self.assertIsNone(b.parse_line('   ', 'x'))

    def test_bad_lines(self):
        for line in ('1.2.3.4:5000', '1.2.3.4:abc:Room', '1.2.3.4:70000:Room', '192.168.0.1:5000:Home', '1.2.3.4:5000:Name  with  spaces'):
            with self.assertRaises(ValueError, msg=line):
                b.parse_line(line, 'x')


class Lobby(unittest.TestCase):
    def test_only_open_rooms_of_version_4(self):
        rooms = b.rooms_of_lobby(lobby({'address': '1.2.3.4'}, {'address': '1.2.3.5', 'hasPassword': True},
                                       {'address': '1.2.3.6', 'netVersion': 3}, {'address': '10.0.0.1'},
                                       {'address': '1.2.3.7', 'port': 'x'}, {'address': '1.2.3.8', 'hasPassword': None}))
        self.assertEqual(rooms, [('1.2.3.4', 24872, 'Room')])


class Build(unittest.TestCase):
    def test_manual_wins_and_exclude_removes(self):
        rooms = [('1.2.3.4', 1, 'Long lobby name'), ('1.2.3.4', 2, 'Other'), ('5.6.7.8', 3, 'Gone')]
        text, _ = b.build(rooms, ['1.2.3.4:1:Short:pw:x', '9.9.9.9:4:Locked'], ['5.6.7.8:3'], [], '2026-11-03', DAY)
        body = b.body_lines(text.splitlines())
        self.assertEqual(body, ['1.2.3.4:1:Short:pw:x', '1.2.3.4:2:Other', '9.9.9.9:4:Locked'])
        self.assertIn('#lobby-rooms 2', text)
        self.assertIn('#titles 2026-11-03', text)

    def test_nothing_changed_then_renewed_after_30_days(self):
        rooms = [('1.2.3.4', 1, 'A')]
        text, _ = b.build(rooms, [], [], [], 't', DAY)
        same, reason = b.build(rooms, [], [], text.splitlines(), 't', DAY + datetime.timedelta(days=29))
        self.assertIsNone(same)
        self.assertEqual(reason, 'nothing changed')
        renewed, _ = b.build(rooms, [], [], text.splitlines(), 't', DAY + datetime.timedelta(days=30))
        self.assertIn('#updated 2026-12-03', renewed)
        newer_titles, _ = b.build(rooms, [], [], text.splitlines(), 'u', DAY + datetime.timedelta(days=1))
        self.assertIn('#titles u', newer_titles)

    def test_a_lobby_that_collapses_is_not_written(self):
        rooms = [('1.2.3.4', p, 'A') for p in range(1, 11)]
        text, _ = b.build(rooms, [], [], [], 't', DAY)
        fewer, reason = b.build(rooms[:4], [], [], text.splitlines(), 't', DAY)
        self.assertIsNone(fewer)
        self.assertIn('not written', reason)
        enough, _ = b.build(rooms[:5], [], [], text.splitlines(), 't', DAY)
        self.assertIsNotNone(enough)

    def test_rooms_per_host_and_size(self):
        rooms = [('1.2.3.4', p, 'A') for p in range(1, 40)]
        text, _ = b.build(rooms, [], [], [], 't', DAY)
        self.assertEqual(len(b.body_lines(text.splitlines())), b.MAX_ROOMS_PER_HOST)
        big = [(f'1.2.{p // 200}.{p % 200 + 1}', 5000, 'x' * 64) for p in range(1200)]
        none, reason = b.build(big, [], [], [], 't', DAY)
        self.assertIsNone(none)
        self.assertIn('more than', reason)


if __name__ == '__main__':
    unittest.main()
