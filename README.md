# SAN Phrases
This script generates and parses English phrases corresponding to SAN chess moves, including some abbreviated phrases that can be parsed to SAN
in context of the board state.

If someone notices a mistake in my logic (that some reasonable phrases cannot be used to deduce the intended move), please open an issue.

## Phrase to SAN
Most valid SAN strings can be abbreviated into a sort of "pseudo-SAN" (ex. when dictated), where knowledge of the board state is sufficient to
deduce the single intended move. For example, the SAN move `Nxf7`, assuming there is an enemy pawn on `f7`, might be spoken in any of the 
following ways:
- `knight takes f 7` (the verbatim spoken SAN)
- `takes` (if there is no other capture in the position)
- `takes f 7` (if there is no other way to capture on `f7`)
- `takes pawn` (if there is no other way to capture a pawn)
- `knight takes` (if there is no other way for a knight to make a capture)
- `knight takes pawn` (if there is no other way for a knight to take a pawn)

In each case above, it is also necessary to make sure another knight cannot take on `f7`.

There are even more cases to consider if the move delivers check, for example `Nxf7+`:
- `knight takes f 7 check` (the verbatim spoken SAN)
- `check` (if there is no other way to deliver check)
- `takes check` (if there is no other way to capture and deliver check)
- `takes pawn check` (if there is no other way to capture a pawn and deliver check)
- `knight takes check` (if there is no other way for a knight to make a capture and deliver check)
- `knight takes pawn check` (if there is no other way for a knight to take a pawn and deliver check)

The Python 3.10 `match` statement comes to the rescue here. I'll skip the detailed analysis of the logic behind each one here. If you want to
fully understand the logic I have implemented, it's probably best to comb through the various `case` statements in `phrase_to_san.py`. Each one
is a noodle in a great big bowl of spaghetti.

## Error Checking
While converting a phrase to SAN using the state of a `chess.Board`, this program does quite a bit of validation. In cases where we cannot simply return
a valid SAN string, there is a hierarchy of custom `Error` and `Warning` types whose bases both inherit from `Exception`. An `Error` type is raised if there is 
no way to convert the phrase to SAN (ex. the move converted from the phrase is not legal in the position; there is missing information, ex. disambiguator or 
promotion piece; or the sequence of tokens in the phrase could otherwise not be parsed). A `Warning` type is raised if the phrase can be narrowed down to 
exactly one legal move, but any of the following are true:
- The user says "check"/"checkmate"/"stalemate" but the move is not check/checkmate/stalemate (or vice versa)
- The user says "takes" but the move is not a capture (or vice versa)
- The user over-disambiguated (ex. "knight b d 7" when "knight d 7" would suffice)
