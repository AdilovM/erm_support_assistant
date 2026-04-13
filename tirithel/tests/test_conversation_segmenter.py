"""Tests for the conversation segmenter."""

from tirithel.processing.conversation_segmenter import ConversationSegmenter


class TestConversationSegmenter:
    def setup_method(self):
        self.segmenter = ConversationSegmenter()

    def test_segment_simple_transcript(self):
        transcript = """Agent: Hello, how can I help you today?
User: I can't find where to change the recording fee.
Agent: Sure, go to Administration, then System Setup.
User: Got it, thank you!"""

        segments = self.segmenter.segment_transcript(transcript)

        assert len(segments) == 4
        assert segments[0].speaker == "support_agent"
        assert segments[1].speaker == "user"
        assert segments[2].speaker == "support_agent"
        assert segments[3].speaker == "user"

    def test_segment_with_timestamps(self):
        transcript = """[10:30:01] Agent: Let me show you how to do this.
[10:30:15] User: Okay, I'm ready.
[10:30:20] Agent: Click on Administration."""

        segments = self.segmenter.segment_transcript(transcript)

        assert len(segments) == 3
        assert segments[0].timestamp is not None
        assert segments[0].speaker == "support_agent"

    def test_guess_segment_type_issue(self):
        assert self.segmenter.guess_segment_type("I can't find the fee settings") == "issue_description"
        assert self.segmenter.guess_segment_type("The report doesn't work properly") == "issue_description"

    def test_guess_segment_type_instruction(self):
        assert self.segmenter.guess_segment_type("Click on Administration menu") == "action_instruction"
        assert self.segmenter.guess_segment_type("Go to System Setup") == "action_instruction"
        assert self.segmenter.guess_segment_type("Navigate to the Financial tab") == "action_instruction"

    def test_guess_segment_type_confirmation(self):
        assert self.segmenter.guess_segment_type("Yes, that's what I needed") == "confirmation"
        assert self.segmenter.guess_segment_type("Thank you so much!") == "confirmation"

    def test_guess_segment_type_clarification(self):
        assert self.segmenter.guess_segment_type("Do you mean the base fee or per-page fee?") == "clarification"

    def test_empty_transcript(self):
        segments = self.segmenter.segment_transcript("")
        assert len(segments) == 0

    def test_multiline_speaker_text(self):
        transcript = """Agent: This is the first line
and this continues on the next line.
User: Got it."""

        segments = self.segmenter.segment_transcript(transcript)

        assert len(segments) == 2
        assert "first line and this continues" in segments[0].text

    def test_normalize_speaker_variants(self):
        transcript = """Support: Hello there.
Customer: Hi, I need help.
Tech: Let me assist you.
Client: Thanks."""

        segments = self.segmenter.segment_transcript(transcript)

        assert segments[0].speaker == "support_agent"
        assert segments[1].speaker == "user"
        assert segments[2].speaker == "support_agent"
        assert segments[3].speaker == "user"
