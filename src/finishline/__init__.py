"""The Whole Field, Called Before the Gun: finish-time and placing predictions published before the gun.

The package is built in the order the prediction is: read the public results
(`ingest`), work out who is who (`identity`), take the course and the weather back out
of every past time (`metrics`, `normalise`), model what is left (`models`), say how sure
it is (`conformal`), turn times into places (`placing`), and score the whole thing
honestly against what a runner could have predicted with a calculator (`backtest`).

Two rules run through all of it, both inherited from the Overload project that the
running arithmetic comes from:

1. **Return None, never a plausible guess.** Every model refuses outside its validity
   range. A missing prediction is recoverable; a confident wrong one is published.
2. **The arithmetic is deterministic and tested.** Nothing here calls a language model.
"""

from __future__ import annotations

__version__ = "0.1.0.dev0"
