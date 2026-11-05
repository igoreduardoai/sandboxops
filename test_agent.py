from agent import execute
R = [execute("bill")["verified"] is True,
     "network disabled" in execute("network_attempt")["sandbox"]["stderr"],
     execute("fork_bomb_ish")["sandbox"]["ok"] is False]
print(R, f"{sum(R)}/{len(R)} passed")
