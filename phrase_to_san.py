import time

import chess
import re

from typing import Optional, Callable, Collection, Type

SQUARE_NAMES = [chess.square_name(s) for s in chess.SQUARES]
FILES = 'abcdefgh'
RANKS = '12345678'
PIECE_NAMES = chess.PIECE_NAMES[1:]
CAPTURABLE_PIECE_NAMES = chess.PIECE_NAMES[1:6]
PROMOTABLE_PIECE_NAMES = chess.PIECE_NAMES[2:6]
NON_PAWN_PIECE_NAMES = chess.PIECE_NAMES[2:7]
CHECKING_PIECE_NAMES = chess.PIECE_NAMES[1:6]


''' Errors '''
class PhraseToSANError(Exception): pass

class UnspecifiedCastlingDirection(PhraseToSANError): pass

class PromotionPieceError(PhraseToSANError): pass
class InvalidPromotionPiece(PhraseToSANError): pass
class UnspecifiedPromotionPiece(PhraseToSANError): pass

class InvalidSourceOrDestination(PhraseToSANError): pass
class InvalidSource(InvalidSourceOrDestination): pass
class InvalidDestination(InvalidSourceOrDestination): pass

class AmbiguousSourceOrDestination(PhraseToSANError): pass
class AmbiguousSource(AmbiguousSourceOrDestination): pass
class AmbiguousDestination(AmbiguousSourceOrDestination): pass

class AmbiguousCaptureSourceOrDestination(PhraseToSANError): pass
class AmbiguousCaptureSource(AmbiguousCaptureSourceOrDestination): pass
class AmbiguousCaptureDestination(AmbiguousCaptureSourceOrDestination): pass

''' Warnings '''
class PhraseToSANWarning(Exception): pass

class IsCheckWarning(PhraseToSANWarning): pass
class IsCheckmateWarning(PhraseToSANWarning): pass
class IsStalemateWarning(PhraseToSANWarning): pass
class IsNotCheckWarning(PhraseToSANWarning): pass
class IsNotCheckmateWarning(PhraseToSANWarning): pass
class IsNotStalemateWarning(PhraseToSANWarning): pass

class IsCaptureWarning(PhraseToSANWarning): pass
class IsNotCaptureWarning(PhraseToSANWarning): pass

class IsNotAmbiguousWarning(PhraseToSANWarning): pass



def phrase_to_san(phrase: str,
                  board: chess.Board,
                  *,
                  raise_warnings: bool = False) -> str:
    """
    Take a spoken-English ``phrase`` and convert it to SAN
    given the state of the provided ``board``.
    """

    from stt_replacements import REPLACEMENTS

    for pattern, replacement in REPLACEMENTS.items():
        phrase = re.sub(pattern, replacement, phrase)
        phrase = phrase.replace(pattern, replacement)

    # def parse_equals_queen(equals_queen: List[str]) -> str | None:
    #     # ``equals_queen``:
    #     #   - May be empty (for moves that are not a promotion)
    #     #   - May start with 'equals'
    #     #   - Must end with a promotable piece (if it's not empty)
    #     if not equals_queen:
    #         return None
    #
    #     if len(equals_queen) not in (1, 2):
    #         raise PhraseToSANError(f'Could not parse phrase: "{phrase}" (invalid tokens: "{equals_queen}")')
    #
    #     if len(equals_queen) == 1:
    #         piece = equals_queen[0]
    #         if piece == 'equals':
    #             raise UnspecifiedPromotionPiece(f'Unspecified promotion piece: "{phrase}"')
    #     else:
    #         equals, piece = equals_queen
    #         if equals != 'equals':
    #             raise PhraseToSANError(f'Could not parse phrase: "{phrase}" (invalid tokens: "{equals}")')
    #
    #     if piece not in PROMOTABLE_PIECE_NAMES:
    #         raise InvalidPromotionPiece(f'Invalid promotion piece: "{piece}"')
    #
    #     return piece


    def get_only_san_where(conditions: Collection[Callable[[chess.Move], bool]],
                           error: Type[PhraseToSANError],
                           error_msg: str,
                           optional_conditions: Collection[Callable[[chess.Move], bool]] = None) -> Optional[str]:
        """
        Given ``board``, get the only SAN move in the position where the given set of ``conditions``
        about the move hold. Takes ``optional_conditions`` that are used to narrow the available moves only
        if multiple are found that match the required ``conditions``. If no such move exists,
        raises ``PhraseToSANError``. If multiple exist, raises the given ``error`` with the given ``error_msg``.
        """
        if optional_conditions is None:
            optional_conditions = []

        candidate_moves = []
        for move in board.legal_moves:
            if any((not condition(move) for condition in conditions)):
                continue

            candidate_moves.append(move)

        if not candidate_moves:
            raise PhraseToSANError('No matching SAN move')
        elif len(candidate_moves) == 1:
            return board.san(candidate_moves[0])
        else:
            if not optional_conditions:
                raise error(error_msg)

            san = None
            for move in candidate_moves:
                if any((not condition(move) for condition in optional_conditions)):
                    continue

                if san is not None:
                    raise error(error_msg)
                san = board.san(move)
            return san

    def gives_check(move: chess.Move) -> bool:
        board.push(move)
        is_check = board.is_check()
        board.pop()
        return is_check

    def gives_mate(move: chess.Move) -> bool:
        board.push(move)
        is_mate = board.is_checkmate()
        board.pop()
        return is_mate

    def gives_stalemate(move: chess.Move) -> bool:
        board.push(move)
        is_stalemate = board.is_stalemate()
        board.pop()
        return is_stalemate

    # Get ready to process token-by-token
    tokens = phrase.lower().split()

    # Take out 'check' / 'checkmate'
    says_check = False
    says_mate = False
    says_stalemate = False
    if tokens[-1] == 'check':
        says_check = True
        check_token = tokens[-1]  # TODO remove these 3 vars?
        del tokens[-1]
    elif tokens[-1] == 'checkmate':
        says_mate = True
        mate_token = tokens[-1]  # (TODO)
        del tokens[-1]
    elif tokens[-1] == 'stalemate':
        says_stalemate = True
        stalemate_token = tokens[-1]  # (TODO)
        del tokens[-1]

    # Lambdas that use check/checkmate as a condition to isolate move
    check_lambda = lambda move: gives_check(move) if says_check else True
    mate_lambda = lambda move: gives_mate(move) if says_mate else True
    stalemate_lambda = lambda move: gives_stalemate(move) if says_stalemate else True
    check_lambdas = (check_lambda, mate_lambda, stalemate_lambda)

    match tokens:
        case ['castles', 'kingside']:
            conditions = (
                lambda move: board.is_castling(move),
                lambda move: board.san(move).startswith('O-O') and 'O-O-O' not in board.san(move),
            )
            san = get_only_san_where(conditions,
                                     PhraseToSANError,
                                     'Cannot kingside castle here',
                                     optional_conditions=check_lambdas)
        case ['castles', 'queenside']:
            conditions = (
                lambda move: board.is_castling(move),
                lambda move: board.san(move).startswith('O-O-O'),
            )
            san = get_only_san_where(conditions,
                                     PhraseToSANError,
                                     'Cannot queenside castle here',
                                     optional_conditions=check_lambdas)
        case ['castles']:
            conditions = (
                lambda move: board.is_castling(move),
            )
            san = get_only_san_where(conditions,
                                     UnspecifiedCastlingDirection,
                                     'Please specify castling direction',
                                     optional_conditions=check_lambdas)
        case [] if any((says_check, says_mate, says_stalemate)):
            conditions = (
                lambda move: board.gives_check(move),
            )
            san = get_only_san_where(conditions,
                                     AmbiguousCaptureSourceOrDestination,
                                     'Multiple checks exist',
                                     optional_conditions=check_lambdas)
        case [piece] if piece in CHECKING_PIECE_NAMES and any((says_check, says_mate, says_stalemate)):
            conditions = (
                lambda move: chess.PIECE_NAMES[board.piece_type_at(move.from_square)] == piece,
                lambda move: board.gives_check(move),
            )
            san = get_only_san_where(conditions,
                                     AmbiguousSourceOrDestination,
                                     f'Multiple {piece} checks exist',
                                     optional_conditions=check_lambdas)
        case [] if says_mate:  # TODO make sure this works
            conditions = (
                gives_mate,
            )
            san = get_only_san_where(conditions,
                                     InvalidSourceOrDestination,
                                     'Multiple checkmates exist',
                                     optional_conditions=check_lambdas)
        case [] if says_check:  # TODO make sure this works
            conditions = (
                gives_check,
            )
            san = get_only_san_where(conditions,
                                     InvalidSourceOrDestination,
                                     'Multiple checks exist',
                                     optional_conditions=check_lambdas)
        case [] if says_stalemate:  # TODO make sure this works
            conditions = (
                gives_stalemate,
            )
            san = get_only_san_where(conditions,
                                     InvalidSourceOrDestination,
                                     'Multiple stalemates exist',
                                     optional_conditions=check_lambdas)
        case ['takes']:
            # TODO: Check that there is only 1 legal capture in the position
            conditions = (
                lambda move: board.is_capture(move),
            )
            san = get_only_san_where(conditions,
                                      AmbiguousSourceOrDestination,
                                      'Multiple captures exist',
                                     optional_conditions=check_lambdas)
        case [from_file, 'takes'] if from_file in FILES:
            # TODO: Check that there is only one legal pawn capture move
            #  where from file is `file`
            conditions = (
                lambda move: board.is_capture(move),
                lambda move: board.piece_type_at(move.from_square) == chess.PAWN,
                lambda move: chess.square_name(move.from_square)[0] == from_file,
            )
            san = get_only_san_where(conditions,
                                      AmbiguousCaptureDestination,
                                      f'There are multiple pawns on the {from_file}-file that can take a piece',
                                     optional_conditions=check_lambdas)
        case ['takes', to_file] if to_file in FILES:
            # TODO: Assume this will only be said for a pawn capture. Check that
            #  there is only one legal pawn capture onto `to_file`
            conditions = (
                lambda move: board.is_capture(move),
                lambda move: board.piece_type_at(move.from_square) == chess.PAWN,
                lambda move: chess.square_name(move.to_square)[0] == to_file,
            )
            san = get_only_san_where(conditions,
                                     AmbiguousCaptureDestination,
                                     f'There are multiple pawns that can take onto the {to_file}-file',
                                     optional_conditions=check_lambdas)

            # For this specific phrase, we are looking first for pawn captures onto the given file,
            # but let's still check that no other piece can capture on the `to_square` for clarity.
            capture_destination = board.parse_san(san).to_square
            for move in board.legal_moves:
                if not board.is_capture(move):
                    continue
                if move.to_square != capture_destination:
                    continue

                if board.san(move) != san:
                    raise AmbiguousCaptureSource(f'Another piece can capture on {chess.square_name(move.to_square)}. '
                                                 f'It seems like you want to take with the pawn, but please clarify.')
        case ['takes', to_file, to_rank] if to_file in FILES and to_rank in RANKS:
            # TODO: Check that there is only one legal capture move to the given square
            conditions = (
                lambda move: board.is_capture(move),
                lambda move: chess.square_name(move.to_square) == f'{to_file}{to_rank}',
            )
            san = get_only_san_where(conditions,
                                     AmbiguousCaptureSource,
                                     f'Multiple pieces can take on {to_file}{to_rank}',
                                     optional_conditions=check_lambdas)
        case ['takes', piece] if piece in CAPTURABLE_PIECE_NAMES:
            # TODO: Check that there is only one legal capture move where
            #  board.piece_type_at(move.to_square) is `piece`
            conditions = (
                lambda move: board.is_capture(move),
                lambda move: chess.PIECE_NAMES[board.piece_type_at(move.to_square)] == piece,
            )
            san = get_only_san_where(conditions,
                                     AmbiguousCaptureSourceOrDestination,
                                     f'Multiple {piece}s can be taken, or multiple pieces can take a {piece}',
                                     optional_conditions=check_lambdas)
        case [piece, 'takes'] if piece in PIECE_NAMES:
            # TODO: Check that there is only one legal capture move where
            #  board.piece_type_at(move.from_square) is `piece`
            conditions = (
                lambda move: board.is_capture(move),
                lambda move: chess.PIECE_NAMES[board.piece_type_at(move.from_square)] == piece,
            )
            san = get_only_san_where(conditions,
                                     AmbiguousCaptureSourceOrDestination,
                                     f'Multiple pieces can be taken by a {piece}, '
                                     f'or multiple {piece}s can take a piece',
                                     optional_conditions=check_lambdas)
        case [piece, 'takes', captured_piece] if piece in PIECE_NAMES and captured_piece in CAPTURABLE_PIECE_NAMES:
            # TODO: Validate that there is only one legal `piece` takes `captured_piece` move
            conditions = (
                lambda move: board.is_capture(move),
                lambda move: chess.PIECE_NAMES[board.piece_type_at(move.from_square)] == piece,
                lambda move: chess.PIECE_NAMES[board.piece_type_at(move.to_square)] == captured_piece,
            )
            san = get_only_san_where(conditions,
                                     AmbiguousCaptureSourceOrDestination,
                                     f'There are multiple ways for a {piece} to take a {captured_piece}',
                                     optional_conditions=check_lambdas)
        case [from_file, *takes, to_file, to_rank] if from_file in FILES and to_file in FILES and to_rank in RANKS:
            # TODO: Check that there is a legal pawn capture, or that this is a UCI move
            #  Note: `takes` should be [], ['takes'], or a [from_rank] for a UCI-formatted move (special case)
            if takes and takes[0] in RANKS:
                # UCI-phrased move
                from_rank = takes[0]
                uci = f'{from_file}{from_rank}{to_file}{to_rank}'
                try:
                    return board.san(chess.Move.from_uci(uci))
                except ValueError:
                    raise PhraseToSANError(f'Phrase was interpreted as UCI, but the move "{uci}" is invalid')
            if takes not in ([], ['takes']):
                raise PhraseToSANError(f'Could not parse phrase: "{phrase}" (invalid tokens: "{takes}")')

            try:
                move = board.push_san(f'{from_file}{to_file}{to_rank}')
                board.pop()
            except ValueError:
                raise PhraseToSANError(f'Invalid pawn capture: "{phrase}"')
            san = board.san(move)
        case [from_file, *takes, to_file] if from_file in FILES and to_file in FILES:
            # TODO: Check that there is only one legal pawn capture from `from_file` to `to_file`
            if takes not in ([], ['takes']):
                raise PhraseToSANError(f'Could not parse phrase: "{phrase}" (invalid tokens: "{takes}")')

            conditions = (
                lambda move: board.is_capture(move),  # This is correct
                lambda move: board.piece_type_at(move.from_square) == chess.PAWN,
                lambda move: chess.square_name(move.from_square)[0] == from_file,
                lambda move: chess.square_name(move.to_square)[0] == to_file,
            )
            san = get_only_san_where(conditions,
                                     AmbiguousCaptureDestination,
                                     f'Multiple pawns on the {from_file}-file can take onto the {to_file}-file',
                                     optional_conditions=check_lambdas)
        case [to_file, to_rank] if to_file in FILES and to_rank in RANKS:
            # TODO: Simple pawn move
            try:
                move = board.push_san(f'{to_file}{to_rank}')
                board.pop()
            except ValueError:
                raise InvalidDestination(f'No pawn can move to {to_file}{to_rank}')
            san = board.san(move)
        case [piece, from_file, from_rank, 'takes', captured_piece] \
                if all((piece in PIECE_NAMES,
                        from_file in FILES,
                        from_rank in RANKS,
                        captured_piece in CAPTURABLE_PIECE_NAMES)):
            # TODO: Make sure there is only one way to  a `captured_piece` with
            #  the `piece` from `{from_file}{from_rank}`
            conditions = (
                lambda move: board.is_capture(move),
                lambda move: chess.square_name(move.from_square) == f'{from_file}{from_rank}',
                lambda move: chess.PIECE_NAMES[board.piece_type_at(move.from_square)] == piece,
                lambda move: chess.PIECE_NAMES[board.piece_type_at(move.to_square)] == captured_piece,
            )
            san = get_only_san_where(conditions,
                                     AmbiguousCaptureDestination,
                                     f'Multiple {captured_piece}s can be taken by the {piece} '
                                     f'on {from_file}{from_rank}',
                                     optional_conditions=check_lambdas)
        case [piece, from_file, from_rank, *takes, to_file, to_rank] \
                if all((piece in PIECE_NAMES,
                        from_file in FILES,
                        from_rank in RANKS,
                        to_file in FILES,
                        to_rank in RANKS)):
            # TODO: Piece move/capture with full-square disamgibuator
            assert piece != 'pawn', 'Internal error: this should have been handled in an earlier match case'

            if takes not in ([], ['takes']):
                raise PhraseToSANError(f'Could not parse phrase: "{phrase}" (invalid tokens: "{takes}")')

            try:
                move = board.push_san(f'{piece[0].upper()}{from_file}{from_rank}{to_file}{to_rank}')
                board.pop()
            except ValueError:
                raise InvalidSourceOrDestination(f'No valid SAN for phrase: "{phrase}"')
            san = board.san(move)
        case [piece, from_file, 'takes', captured_piece] \
                if all((piece in PIECE_NAMES,
                        from_file in FILES,
                        captured_piece in CAPTURABLE_PIECE_NAMES)):
            # TODO: Piece move/capture with file disambiguator. Make sure no further disambiguator is required
            #  by trying to push SAN
            assert piece != 'pawn', 'Internal error: this should have been handled in an earlier match case'

            conditions = (
                lambda move: board.is_capture(move),
                lambda move: chess.PIECE_NAMES[board.piece_type_at(move.from_square)] == piece,
                lambda move: chess.square_name(move.from_square)[0] == from_file,
                lambda move: chess.PIECE_NAMES[board.piece_type_at(move.to_square)] == captured_piece,
            )
            san = get_only_san_where(conditions,
                                     AmbiguousCaptureSourceOrDestination,
                                     f'There are multiple ways for a {piece} on the {from_file}-file '
                                     f'to take a {captured_piece}',
                                     optional_conditions=check_lambdas)
        case [piece, from_file, *takes, to_file, to_rank] \
                if all((piece in PIECE_NAMES,
                        from_file in FILES,
                        to_file in FILES,
                        to_rank in RANKS)):
            # TODO: Make sure there is only one way to move/capture onto `{to_rank}{to_file}`
            #  with a `piece` on `from_file`
            if takes not in ([], ['takes']):
                raise PhraseToSANError(f'Could not parse phrase: "{phrase}" (invalid tokens: "{takes}")')

            conditions = (
                lambda move: chess.PIECE_NAMES[board.piece_type_at(move.from_square)] == piece,
                lambda move: chess.square_name(move.from_square)[0] == from_file,
                lambda move: chess.square_name(move.to_square) == f'{to_file}{to_rank}',
            )
            san = get_only_san_where(conditions,
                                     AmbiguousCaptureSource,
                                     f'Multiple {piece}s from the {from_file}-file can take on {to_file}{to_rank}',
                                     optional_conditions=check_lambdas)
        case [piece, from_rank, 'takes', captured_piece] \
                if all((piece in PIECE_NAMES,
                        from_rank in RANKS,
                        captured_piece in CAPTURABLE_PIECE_NAMES)):
            # TODO: Piece move/capture with rank disambiguator. Make sure no further disambiguator is required
            #  by trying to push SAN
            assert piece != 'pawn', 'Internal error: this should have been handled in an earlier match case'

            conditions = (
                lambda move: board.is_capture(move),
                lambda move: chess.PIECE_NAMES[board.piece_type_at(move.from_square)] == piece,
                lambda move: chess.square_name(move.from_square)[1] == from_rank,
                lambda move: chess.PIECE_NAMES[board.piece_type_at(move.to_square)] == captured_piece,
            )
            san = get_only_san_where(conditions,
                                     AmbiguousCaptureSourceOrDestination,
                                     f'There are multiple ways for a {piece} on the rank {from_rank} '
                                     f'to take a {captured_piece}',
                                     optional_conditions=check_lambdas)
        case [piece, from_rank, *takes, to_file, to_rank] \
                if all((piece in PIECE_NAMES,
                        from_rank in RANKS,
                        to_file in FILES,
                        to_rank in RANKS)):
            # TODO: Make sure there is only one way to move/capture onto `{to_rank}{to_file}`
            #  with a `piece` on `from_file`
            assert piece != 'pawn', 'Internal error: this should have been handled in an earlier match case'

            if takes not in ([], ['takes']):
                raise PhraseToSANError(f'Could not parse phrase: "{phrase}" (invalid tokens: "{takes}")')

            conditions = (
                lambda move: chess.PIECE_NAMES[board.piece_type_at(move.from_square)] == piece,
                lambda move: chess.square_name(move.from_square)[0] == from_rank,
                lambda move: chess.square_name(move.to_square) == f'{to_file}{to_rank}',
            )
            san = get_only_san_where(conditions,
                                     AmbiguousCaptureSource,
                                     f'Multiple {piece}s from rank {from_rank} can take on {to_file}{to_rank}',
                                     optional_conditions=check_lambdas)
        case [piece, 'takes', captured_piece] \
                if all((piece in PIECE_NAMES,
                        captured_piece in CAPTURABLE_PIECE_NAMES)):
            # TODO: Simple piece/pawn move/capture with no disambiguator. Make sure no
            #  further disambiguator is required by trying to push the SAN
            assert piece != 'pawn', 'Internal error: this should have been handled in an earlier match case'

            conditions = (
                lambda move: chess.PIECE_NAMES[board.piece_type_at(move.from_square)] == piece,
                lambda move: chess.PIECE_NAMES[board.piece_type_at(move.to_square)] == captured_piece,
            )
            san = get_only_san_where(conditions,
                                     AmbiguousCaptureSourceOrDestination,
                                     f'There are multiple ways for a {piece} to take a {captured_piece}',
                                     optional_conditions=check_lambdas)
        case [piece, *takes, to_file, to_rank] \
                if all((piece in PIECE_NAMES,
                        to_file in FILES,
                        to_rank in RANKS)):
            # TODO: Make sure there is only one way to move/capture onto `{to_rank}{to_file}` with a `piece`
            conditions = (
                lambda move: chess.PIECE_NAMES[board.piece_type_at(move.from_square)] == piece,
                lambda move: chess.square_name(move.to_square) == f'{to_file}{to_rank}',
            )
            san = get_only_san_where(conditions,
                                     AmbiguousCaptureSource,
                                     f'Multiple {piece}s can take on {to_file}{to_rank}',
                                     optional_conditions=check_lambdas)
        case _:
            raise PhraseToSANError(f'Could not parse phrase: "{phrase}"')

    if raise_warnings:
        board.push_san(san)
        is_mate = board.is_checkmate()
        is_check = board.is_check()
        is_stalemate = board.is_stalemate()
        board.pop()

        if is_mate and not says_mate:
            assert san[-1] == '#'
            raise IsCheckmateWarning(f'{san[:-1]} gives checkmate ({san}), but you did not say "checkmate"')
        elif not is_mate and says_mate:
            # noinspection PyUnboundLocalVariable
            raise IsNotCheckmateWarning(f'{san} does not give checkmate, but you said "{mate_token}"')
        elif is_check and not says_check:
            assert san[-1] == '+'
            raise IsCheckWarning(f'{san[:-1]} gives check ({san}), but you did not say "check"')
        elif not is_check and says_check:
            # noinspection PyUnboundLocalVariable
            raise IsNotCheckWarning(f'{san} does not give check, but you said "{check_token}"')
        elif is_stalemate and not says_stalemate:
            raise IsStalemateWarning(f'{san} gives stalemate, but you did not say "stalemate"')
        elif not is_stalemate and says_stalemate:
            # noinspection PyUnboundLocalVariable
            raise IsNotStalemateWarning(f'{san} does not give stalemate, but you said "{stalemate_token}"')

    return san

def main():
    b = chess.Board()
    flipped = False

    USE_SVG = True
    '''Whether to print the board (for the CLI) or render an SVG after each move (for Jupyter).'''

    RAISE_WARNINGS = True
    '''
    Whether to reject phrases that can narrowed down to only one legal move, but where one of the following is true:
    - The user says "check"/"checkmate"/"stalemate" but the move is not check/checkmate/stalemate (or vice versa)
    - The user says "takes" but the move is not a capture (or vice versa)
    - The user over-disambiguated (ex. "knight b d 7" when "knight d 7" would suffice)
    '''

    ALLOW_SAN = True
    '''Shortcut for the CLI - input SAN moves separated by spaces instead of a phrase'''


    output = ''
    SENTINELS = ['stop', 'done', 'exit', 'quit', 'break']
    while True:
        if USE_SVG:
            yield b, flipped, output
            time.sleep(0.1)
        else:
            print(b if not flipped else b.transform(chess.flip_vertical).transform(chess.flip_horizontal))

        phrase = input('Enter a move as a spoken-English phrase:\n>>> ')
        if phrase in SENTINELS:
            break

        if phrase == 'reset':
            b = chess.Board()
            continue
        elif phrase == 'flip':
            flipped = not flipped
            continue
        elif phrase == 'pop':
            b.pop()
            continue

        if ALLOW_SAN:
            try:
                for san in phrase.split():
                    b.push_san(san)
                continue
            except ValueError:
                pass
        try:
            san = phrase_to_san(phrase, b, raise_warnings=RAISE_WARNINGS)
            output = f'SAN: {san}'
            b.push_san(san)
        except PhraseToSANError as e:
            output = f'Error: {str(e)}'
        except PhraseToSANWarning as e:
            output = f'Warning: {str(e)}'

        if not USE_SVG:
            print(output)


if __name__ == '__main__':
    main()
