from types import SimpleNamespace

from app.core import config
from app.services.topic_research import (
    OpenAITopicResearchUnavailable,
    TopicResearchRequest,
    build_mock_topic_ideas,
    research_topics,
)


def test_mock_topic_research_returns_three_apply_ready_ideas(monkeypatch):
    monkeypatch.setattr(config.settings, "openai_api_key", None)

    response = research_topics(
        TopicResearchRequest(
            niche=" healthy meal prep ",
            audience="new   parents",
            goal="save time on weeknight dinners",
        )
    )

    assert response.provider == "mock-topic-research"
    assert len(response.ideas) == 3
    assert [idea.title for idea in response.ideas] == [
        "The biggest myth about healthy meal prep",
        "3 mistakes people make with healthy meal prep",
        "A simple workflow for healthy meal prep",
    ]
    assert response.ideas[1].angle == "Common mistakes angle for new parents."
    assert response.ideas[1].image_prompt == (
        "three clean mistake cards floating around a central creator workstation "
        "about healthy meal prep for new parents, modern creator education style, "
        "polished social video thumbnail"
    )
    assert response.ideas[1].negative_prompt == (
        "tiny unreadable text, watermark, cluttered layout, distorted hands"
    )
    assert response.ideas[1].motion_prompt == (
        "Cards slide in one by one, subtle camera push, clear readable composition, "
        "optimized for a short explainer video"
    )
    assert response.ideas[1].narration == (
        "Here are three mistakes to avoid when working on healthy meal prep. "
        "In the next few seconds, I’ll show new parents how to save time on weeknight dinners."
    )
    assert response.ideas[1].style == "Design"
    assert response.ideas[1].aspect_ratio == "9:16"
    assert response.ideas[1].image_option_count == 3


def test_openai_topic_research_parses_three_ideas(monkeypatch):
    monkeypatch.setattr(config.settings, "openai_api_key", "test-key")

    class FakeChatCompletions:
        def create(self, **kwargs):
            assert kwargs["model"] == config.settings.openai_topic_model
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=(
                                '{"ideas": ['
                                '{"id":"trend","title":"Trend","hook":"Trend hook",'
                                '"angle":"Trend angle","image_prompt":"Trend image",'
                                '"negative_prompt":"watermark","motion_prompt":"Trend motion",'
                                '"narration":"Trend narration","style":"Design",'
                                '"aspect_ratio":"9:16","image_option_count":3},'
                                '{"id":"mistake","title":"Mistake","hook":"Mistake hook",'
                                '"angle":"Mistake angle","image_prompt":"Mistake image",'
                                '"negative_prompt":"watermark","motion_prompt":"Mistake motion",'
                                '"narration":"Mistake narration","style":"Photographic",'
                                '"aspect_ratio":"9:16","image_option_count":2},'
                                '{"id":"workflow","title":"Workflow","hook":"Workflow hook",'
                                '"angle":"Workflow angle","image_prompt":"Workflow image",'
                                '"negative_prompt":"watermark","motion_prompt":"Workflow motion",'
                                '"narration":"Workflow narration","style":"Cinematic",'
                                '"aspect_ratio":"16:9","image_option_count":1}'
                                "]}"
                            )
                        )
                    )
                ]
            )

    class FakeOpenAI:
        def __init__(self, api_key):
            assert api_key == "test-key"
            self.chat = SimpleNamespace(completions=FakeChatCompletions())

    monkeypatch.setattr("app.services.topic_research.OpenAI", FakeOpenAI)

    response = research_topics(
        TopicResearchRequest(niche="creator workflows", audience="founders", goal="ship faster")
    )

    assert response.provider == "openai"
    assert [idea.id for idea in response.ideas] == ["trend", "mistake", "workflow"]
    assert response.ideas[0].title == "Trend"


def test_openai_topic_research_falls_back_on_bad_shape(monkeypatch):
    monkeypatch.setattr(config.settings, "openai_api_key", "test-key")
    monkeypatch.setattr("app.services.topic_research.research_topics_with_openai", _raise_bad_shape)

    response = research_topics(
        TopicResearchRequest(niche="creator workflows", audience="founders", goal="ship faster")
    )

    assert response.provider == "mock-topic-research"
    assert response.ideas == build_mock_topic_ideas(
        TopicResearchRequest(niche="creator workflows", audience="founders", goal="ship faster")
    )


def _raise_bad_shape(request):
    raise OpenAITopicResearchUnavailable(f"bad topic response for {request.niche}")
