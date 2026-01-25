from checkngn.utils import normalize_action

# Test cases
print("String:", normalize_action("notify_manager"))
print("List (single action):", normalize_action(["put_on_sale", {"percent": 25}]))
print("Dict:", normalize_action({"action": "log_event", "params": {"id": 1}}))

print("List of actions (dicts):", normalize_action([{"action": "a"}, {"action": "b"}]))
print("List of actions (mixed):", normalize_action(["notify", ["sale", {"p": 10}], {"action": "log"}]))
