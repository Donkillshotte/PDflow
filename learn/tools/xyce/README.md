# Xyce integration

The Xyce helper is an optional current-run probe. It accepts a deck generated
from the selected mesh and writes status, command, inputs, and outputs in the
run scope. If the executable or model is absent it returns `GAP`.

It never imports an output from another run. Compare Xyce and another solver
only when their current decks and mesh fingerprints match.
