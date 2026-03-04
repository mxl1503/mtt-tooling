from __future__ import annotations


def paid_and_bust_probabilities(itm_rate: float, number_paid: int) -> tuple[float, float, bool]:
    """
    Return (each_paid_probability, bust_probability, floored_to_zero_warning).

    Follows the requested simple model:
      - all paid placements are equally likely
      - bust probability is 1 - ITM%
    For edge cases where floor(num_players * ITM%) == 0, this returns
    paid probability 0 and bust probability 1 to keep probabilities valid.
    """
    itm_rate = min(max(float(itm_rate), 0.0), 1.0)

    if number_paid <= 0:
        return 0.0, 1.0, True

    each_paid_probability = itm_rate / number_paid
    bust_probability = 1.0 - itm_rate
    return each_paid_probability, bust_probability, False

