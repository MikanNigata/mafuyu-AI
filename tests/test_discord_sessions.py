import unittest

from mafuyu_ai.interfaces import discord as discord_interface


class DiscordSessionTests(unittest.TestCase):
    def setUp(self):
        discord_interface.sessions.clear()

    def tearDown(self):
        discord_interface.sessions.clear()

    def test_guild_sessions_are_isolated_by_user(self):
        first = discord_interface.get_session(guild_id=10, user_id=1)
        second = discord_interface.get_session(guild_id=10, user_id=2)

        self.assertIsNot(first, second)

    def test_same_context_reuses_session(self):
        first = discord_interface.get_session(guild_id=10, user_id=1)
        second = discord_interface.get_session(guild_id=10, user_id=1)

        self.assertIs(first, second)


if __name__ == "__main__":
    unittest.main()
