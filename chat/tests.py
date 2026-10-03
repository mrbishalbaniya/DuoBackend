"""Chat moderation tests: matcher, REST send, WebSocket send/edit."""

from unittest import mock

from asgiref.sync import sync_to_async
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import Profile
from chat.models import Conversation, Message
from chat.routing import websocket_urlpatterns
from duo_project.security.moderation_lexicon import Category, Severity
from duo_project.security.text_moderation import (
    INAPPROPRIATE_CODE,
    INAPPROPRIATE_MESSAGE,
    moderate_text,
    normalize_text,
)
from matching.models import Match

User = get_user_model()

TEST_SETTINGS = dict(
    CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
    CHAT_MODERATION_ENABLED=True,
    CHAT_MODERATION_BLOCK_SEVERITY="MEDIUM",
)


def blocked(text):
    return not moderate_text(text).allowed


# --------------------------------------------------------------------------- #
# Matcher
# --------------------------------------------------------------------------- #


@override_settings(**TEST_SETTINGS)
class ModerationMatcherTests(SimpleTestCase):
    def assertBlocked(self, *texts):
        for t in texts:
            with self.subTest(text=t):
                self.assertTrue(blocked(t), f"expected block: {t!r}")

    def assertAllowed(self, *texts):
        for t in texts:
            with self.subTest(text=t):
                self.assertFalse(blocked(t), f"expected allow: {t!r}")

    def test_english_abuse(self):
        self.assertBlocked("fuck you", "you bitch", "what an asshole", "shut up you cunt", "stfu")

    def test_romanized_nepali_abuse(self):
        self.assertBlocked("muji", "machikne", "randi", "harami", "tero aama lai chikchu", "madarchod")

    def test_devanagari_nepali_abuse(self):
        self.assertBlocked("मुजी", "रण्डी", "हरामी", "जाठा", "मादरचोद")

    def test_hindi_abuse(self):
        self.assertBlocked(
            "kamina", "haramzada", "bhenchod", "bahinchod", "teri maa ki", "maa ki chut",
            "bhosdiwala", "lavde", "chhinal",
            "कमीना", "हरामज़ादा", "बहनचोद", "छिनाल",
        )

    def test_bhojpuri_abuse(self):
        self.assertBlocked("tohar maai ke", "maai chod", "lundwa", "chhinar", "तोहार माई के", "छिनार")

    def test_more_nepali_and_english(self):
        self.assertBlocked(
            "chikeko", "madise", "मधिसे", "थोकिदिन्छु",
            "douchebag", "cocksucker", "sandnigger", "you should die",
        )

    def test_threats_hindi_bhojpuri_nepali(self):
        self.assertBlocked(
            "jaan se maar dunga", "tujhe maar dunga", "jaan maar deb",
            "khattam garidinchu", "जान से मार दूंगा", "मार डालूंगा", "I'll stab you",
        )

    def test_clean_hindi_bhojpuri_nepali(self):
        self.assertAllowed(
            "aap kaise ho", "mujhe chutti chahiye", "kya chhoot milegi", "chutney",
            "tohar naam ka ba", "ka haal ba", "maiya ke pranam", "jhatka",
            "Lund University", "dhoti kurta", "mero kukur cute cha", "kutte ko khana diyo",
            "आप कैसे हो", "तोहार नाम का बा", "तपाईंलाई कस्तो छ",
        )

    def test_case_variations(self):
        self.assertBlocked("FUCK", "FuCk", "MUJI", "Bitch")

    def test_spacing_variations(self):
        self.assertBlocked("f u c k", "m u j i", "f  u  c  k off", "f . u . c . k")

    def test_punctuation_between_characters(self):
        self.assertBlocked("f.u.c.k", "f-u-c-k", "f_u_c_k", "b.i.t.c.h", "f*ck")

    def test_repeated_characters(self):
        self.assertBlocked("fuuuuuck", "biiiitch", "mujiii", "mujeee", "shiiit")

    def test_character_substitutions(self):
        self.assertBlocked("sh1t", "$hit", "b!tch", "a$$hole", "fvck", "n1gger")

    def test_unicode_normalization(self):
        self.assertBlocked(
            "ｆｕｃｋ",  # full-width
            "fuсk",  # Cyrillic "с"
            "f​uck",  # zero-width space
            "fúck",  # accent
            "रंडी",  # anusvara spelling
            "मुजीीी",  # repeated vowel sign
        )

    def test_word_split_in_two(self):
        self.assertBlocked("fu ck", "bit ch", "मु जी")

    def test_more_obfuscation(self):
        self.assertBlocked("ƒuck", "fυck", "f🙂u🙂c🙂k", "f" + chr(10) + "u" + chr(10) + "c" + chr(10) + "k", "𝐟𝐮𝐜𝐤", "ⓕⓤⓒⓚ", "rаndi", "5lut")

    def test_contractions_do_not_create_false_positives(self):
        self.assertAllowed("who're you?", "she'll call later", "we're going out", "push it", "a bit chilly")
        self.assertBlocked("I'll kill you", "I'm going to kill you")

    def test_suffixes_and_inflections(self):
        self.assertBlocked("bitches", "fucking", "motherfucker", "mujiko", "रण्डीको")

    def test_multi_word_phrases(self):
        self.assertBlocked(
            "kill yourself",
            "go kill   yourself",
            "I'll kill you",
            "i will rape you",
            "send nudes",
            "kukur ko chhora",
            "कुकुरको छोरा",
            "gu kha",
            "मारिदिन्छु",
        )

    def test_clean_messages_allowed(self):
        self.assertAllowed(
            "Hi! How was your day?",
            "I love you",
            "you look so sexy tonight",
            "do you want to have sex later?",
            "let's kiss",
            "class assignment",
            "assessment tomorrow",
            "Scunthorpe",
            "therapist appointment",
            "grape juice",
            "shitake mushrooms",
            "bitter coffee",
            "pass the bass",
            "as you wish",
            "I'm ill today",
            "I could kill for a pizza",
            "mero aama kasto hunuhunchha",
            "tero ghar kaha ho",
            "मलाई तिमी मन पर्छ",
            "Kathmandu ma bhetaun",
            "",
            "   ",
        )

    def test_low_severity_is_flagged_not_blocked(self):
        result = moderate_text("you are so stupid")
        self.assertTrue(result.allowed)
        self.assertTrue(result.flagged)
        self.assertEqual(result.category, Category.INSULT)

    def test_severity_and_category_reported(self):
        result = moderate_text("i will kill you")
        self.assertFalse(result.allowed)
        self.assertEqual(result.category, Category.THREAT)
        self.assertEqual(result.severity, Severity.HIGH)

    @override_settings(CHAT_MODERATION_BLOCK_SEVERITY="HIGH")
    def test_threshold_is_configurable(self):
        self.assertFalse(blocked("you bitch"))  # MEDIUM passes a HIGH threshold
        self.assertTrue(blocked("i will kill you"))

    @override_settings(CHAT_MODERATION_ENABLED=False)
    def test_can_be_disabled(self):
        self.assertFalse(blocked("fuck"))

    def test_normalize_text(self):
        self.assertEqual(normalize_text("ＦÚСК"), "fuck")

    def test_result_never_exposes_matched_word(self):
        result = moderate_text("fuck")
        self.assertNotIn("fuck", repr(result))


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def make_pair():
    a = User.objects.create_user(username="mod_a", email="a@example.com", password="Kathmandu7!")
    b = User.objects.create_user(username="mod_b", email="b@example.com", password="Kathmandu7!")
    Profile.objects.get_or_create(user=a, defaults={"full_name": "Asha"})
    Profile.objects.get_or_create(user=b, defaults={"full_name": "Bikash"})
    match = Match.objects.create(user1=a, user2=b)
    convo, _ = Conversation.objects.get_or_create(match=match)
    return a, b, convo


# --------------------------------------------------------------------------- #
# REST
# --------------------------------------------------------------------------- #


@override_settings(**TEST_SETTINGS)
class ModerationRestTests(TestCase):
    def setUp(self):
        self.a, self.b, self.convo = make_pair()
        self.client = APIClient()
        self.client.force_authenticate(self.a)
        self.url = f"/api/chat/conversations/{self.convo.public_id}/messages/"

    @mock.patch("notifications.dispatch.dispatch_chat_message_push")
    @mock.patch("chat.views.broadcast_chat_message")
    def test_abusive_message_rejected(self, broadcast, push):
        res = self.client.post(self.url, {"content": "f.u.c.k you"}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["code"], INAPPROPRIATE_CODE)
        self.assertEqual(res.data["detail"], INAPPROPRIATE_MESSAGE)
        self.assertEqual(res.data["message"], INAPPROPRIATE_MESSAGE)
        self.assertFalse(Message.objects.filter(conversation=self.convo).exists())
        broadcast.assert_not_called()
        push.assert_not_called()

    @mock.patch("notifications.dispatch.dispatch_chat_message_push")
    @mock.patch("chat.views.broadcast_chat_message")
    def test_nepali_message_rejected(self, broadcast, push):
        res = self.client.post(self.url, {"content": "तँ मुजी"}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertFalse(Message.objects.filter(conversation=self.convo).exists())
        push.assert_not_called()

    @mock.patch("notifications.dispatch.dispatch_chat_message_push")
    @mock.patch("chat.views.broadcast_chat_message")
    def test_clean_message_saved(self, broadcast, push):
        res = self.client.post(self.url, {"content": "Hey, coffee this weekend?"}, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(Message.objects.filter(conversation=self.convo).count(), 1)
        broadcast.assert_called_once()
        push.assert_called_once()

    def test_error_does_not_leak_dictionary(self):
        res = self.client.post(self.url, {"content": "randi"}, format="json")
        self.assertNotIn("randi", str(res.data).lower())

    def test_edit_service_refuses_abuse(self):
        from chat.services import edit_message
        from duo_project.security.text_moderation import InappropriateContent

        msg = Message.objects.create(conversation=self.convo, sender=self.a, content="hello")
        with self.assertRaises(InappropriateContent):
            edit_message(msg, self.a, "you bitch")
        msg.refresh_from_db()
        self.assertEqual(msg.content, "hello")


# --------------------------------------------------------------------------- #
# WebSocket
# --------------------------------------------------------------------------- #


@override_settings(**TEST_SETTINGS)
class ModerationWebSocketTests(TransactionTestCase):
    def setUp(self):
        self.a, self.b, self.convo = make_pair()

    async def _connect(self, user):
        comm = WebsocketCommunicator(URLRouter(websocket_urlpatterns), f"/ws/chat/{self.convo.public_id}/")
        comm.scope["user"] = user
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        hello = await comm.receive_json_from(timeout=3)
        self.assertEqual(hello["type"], "connected")
        return comm

    async def _drain(self, comm):
        """Skip connect-time events (e.g. delivery receipts)."""
        events = []
        while not await comm.receive_nothing(timeout=0.3):
            events.append(await comm.receive_json_from())
        return events

    @mock.patch("notifications.dispatch.dispatch_chat_message_push")
    async def test_ws_abusive_message_rejected_not_broadcast(self, push):
        sender = await self._connect(self.a)
        receiver = await self._connect(self.b)
        await self._drain(sender)
        await self._drain(receiver)

        await sender.send_json_to(
            {"type": "chat_message", "content": "F U C K you", "client_temp_id": "tmp-1"}
        )
        err = await sender.receive_json_from(timeout=3)
        self.assertEqual(err["type"], "error")
        self.assertEqual(err["code"], INAPPROPRIATE_CODE)
        self.assertEqual(err["message"], INAPPROPRIATE_MESSAGE)
        self.assertEqual(err["client_temp_id"], "tmp-1")

        # Nothing reached the other person and nothing was stored or pushed.
        self.assertTrue(await receiver.receive_nothing(timeout=0.5))
        count = await sync_to_async(Message.objects.filter(conversation=self.convo).count)()
        self.assertEqual(count, 0)
        push.assert_not_called()

        await sender.disconnect()
        await receiver.disconnect()

    @mock.patch("notifications.dispatch.dispatch_chat_message_push")
    async def test_ws_clean_message_delivered(self, push):
        sender = await self._connect(self.a)
        await self._drain(sender)
        await sender.send_json_to(
            {"type": "chat_message", "content": "Namaste! kasto cha?", "client_temp_id": "tmp-2"}
        )
        # Inbox events (e.g. conversation_updated) may interleave; read until both arrive.
        types = set()
        for _ in range(6):
            types.add((await sender.receive_json_from(timeout=3))["type"])
            if {"chat_message", "message_ack"} <= types:
                break
        self.assertIn("chat_message", types)
        self.assertIn("message_ack", types)
        count = await sync_to_async(Message.objects.filter(conversation=self.convo).count)()
        self.assertEqual(count, 1)
        await sender.disconnect()

    async def test_ws_edit_to_abuse_rejected(self):
        msg = await sync_to_async(Message.objects.create)(
            conversation=self.convo, sender=self.a, content="hello"
        )
        sender = await self._connect(self.a)
        await self._drain(sender)
        await sender.send_json_to({"type": "edit_message", "id": msg.id, "content": "muji"})
        err = await sender.receive_json_from(timeout=3)
        self.assertEqual(err["code"], INAPPROPRIATE_CODE)
        await sync_to_async(msg.refresh_from_db)()
        self.assertEqual(msg.content, "hello")
        await sender.disconnect()


# --------------------------------------------------------------------------- #
# Per-chat "Filter offensive language" (receiver's setting)
# --------------------------------------------------------------------------- #


@override_settings(**TEST_SETTINGS)
class ModerationPreferenceTests(TestCase):
    def setUp(self):
        self.a, self.b, self.convo = make_pair()
        self.client = APIClient()
        self.url = f"/api/chat/conversations/{self.convo.public_id}/messages/"
        self.settings_url = f"/api/chat/conversations/{self.convo.public_id}/settings/"

    def _set_filter(self, user, enabled):
        self.client.force_authenticate(user)
        res = self.client.patch(self.settings_url, {"filter_offensive": enabled}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["filter_offensive"], enabled)

    def _send_as(self, user, text):
        self.client.force_authenticate(user)
        with mock.patch("chat.views.broadcast_chat_message"), mock.patch(
            "notifications.dispatch.dispatch_chat_message_push"
        ):
            return self.client.post(self.url, {"content": text}, format="json")

    def test_default_is_on(self):
        self.assertEqual(self._send_as(self.a, "what the fuck").status_code, 400)

    def test_receiver_can_allow_profanity(self):
        self._set_filter(self.b, False)  # b receives
        self.assertEqual(self._send_as(self.a, "what the fuck").status_code, 201)
        self.assertEqual(self._send_as(self.a, "kamina").status_code, 201)

    def test_threats_hate_and_harassment_stay_blocked(self):
        self._set_filter(self.b, False)
        for text in ("i will kill you", "kill yourself", "send nudes", "nigger", "जान से मार दूंगा"):
            with self.subTest(text=text):
                self.assertEqual(self._send_as(self.a, text).status_code, 400)

    def test_sender_cannot_disable_it_for_themselves(self):
        self._set_filter(self.a, False)  # sender turns it off: no effect on what b receives
        self.assertEqual(self._send_as(self.a, "what the fuck").status_code, 400)

    def test_setting_is_per_direction(self):
        self._set_filter(self.b, False)
        self.assertEqual(self._send_as(self.a, "fuck").status_code, 201)  # to b: allowed
        self.assertEqual(self._send_as(self.b, "fuck").status_code, 400)  # to a: still filtered

    def test_conversation_payload_exposes_setting(self):
        self._set_filter(self.b, False)
        self.client.force_authenticate(self.b)
        res = self.client.get(f"/api/chat/conversations/{self.convo.public_id}/")
        self.assertEqual(res.status_code, 200)
        self.assertIs(res.data["filter_offensive"], False)

    def test_engine_never_relaxes_safety_categories(self):
        everything = frozenset(Category)
        self.assertFalse(moderate_text("i will kill you", ignore=everything).allowed)
        self.assertTrue(moderate_text("fuck", ignore=everything).allowed)
