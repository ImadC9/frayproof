from copy import deepcopy

from hypothesis import given, settings
from hypothesis import strategies as st

from frayproof import Contract, check, validate

from .conftest import call, result, user


@st.composite
def sessions(draw):
    count = draw(st.integers(min_value=0, max_value=15))
    messages = [{"role": "system", "content": "Keep this instruction."}]
    for i in range(count):
        messages.append(user(draw(st.text(alphabet="abc XYZ012éمرحبا\n", max_size=40))))
        size = draw(st.integers(min_value=1, max_value=4))
        ids = [f"call_{i}_{j}" for j in range(size)]
        messages.append(call(*ids))
        order = draw(st.permutations(ids))
        messages.extend(
            result(id_, draw(st.text(alphabet="abc XYZ012éمرحبا\n", max_size=50))) for id_ in order
        )
    return messages


@given(sessions())
@settings(max_examples=120)
def test_generated_valid_sessions_pass(messages):
    assert validate(messages).passed


@given(sessions())
@settings(max_examples=80)
def test_whole_exchange_removal_is_legitimate(messages):
    contract = Contract.model_validate({"pins": [{"name": "instructions", "role": "system"}]})
    assert check(messages, [messages[0]], contract).passed


@given(sessions().filter(lambda messages: len(messages) > 1))
@settings(max_examples=80)
def test_dropping_only_call_is_detected(messages):
    after = deepcopy(messages)
    del after[2]
    assert not validate(after).passed


@given(sessions())
@settings(max_examples=80)
def test_pinned_instruction_loss_always_detected(messages):
    contract = Contract.model_validate({"pins": [{"name": "instructions", "role": "system"}]})
    assert not check(messages, messages[1:], contract).passed
