# ver. 1.0.10
import datetime
import os
import re
import lichess.api
from lichess.format import SINGLE_PGN
import chess
import chess.pgn
from io import StringIO
import telebot
from fentoboardimage import fenToImage, loadPiecesFolder
import berserk
import json
from datetime import datetime, timezone

##################################
with open('config.jsonc') as config_file:
    config_data = json.load(config_file)
token = config_data['token']
StudyID = config_data['StudyID']
ChapterWhiteId = config_data['ChapterWhiteId']
ChapterBlackId = config_data['ChapterBlackId']
TelegramToken = config_data["TelegramToken"]
nicknames = config_data["nicknames"]
Openings = config_data["Openings"]
#############################

def SendImageToBot(bot, ID_MESSAGE, flipped, FEN):
    if not os.path.exists("./pieces"):
         print("Загрузите картинки фигур в папку './pieces'")
         return
    boardImage = fenToImage(fen=FEN,squarelength=100,pieceSet=loadPiecesFolder("./pieces"),darkColor="#D18B47",lightColor="#FFCE9E",flipped=flipped)
    bot.send_photo(ID_MESSAGE, boardImage)
def GetMovesByFEN(FEN):
    if FEN not in Openings:
        return  None
    moves = Openings[FEN].split()
    root_node = chess.pgn.Game()
    for move in moves:
        root_node = root_node.add_variation(chess.Move.from_uci(move))
    return root_node.variations[0]

def moveWithDot(Move):
    return str(Move // 2 + Move % 2) + ("." if Move % 2 == 1 else "...")
def SendMessageToBot(bot, ID_MESSAGE, games_moves, isColorWhite, node, text ):
    bot.send_message(ID_MESSAGE, games_moves, parse_mode='HTML')
    bot.send_message(ID_MESSAGE, '<b>' + text + '</b>', parse_mode='HTML')
    SendImageToBot(bot, ID_MESSAGE, not isColorWhite, node.board().board_fen())

session = berserk.TokenSession(token)
client = berserk.Client(session=session)
WhiteTheory = client.studies.export_chapter(study_id=StudyID, chapter_id=ChapterWhiteId)
BlackTheory = client.studies.export_chapter(study_id=StudyID, chapter_id=ChapterBlackId)
bot = telebot.TeleBot(TelegramToken)
print("Bot running...")
@bot.message_handler(commands=['start'])
def start(message):
    procesed_game = ""
    while True:
        try:
            game_nickname = ""
            moveCount = 0
            PrevMove = ""
            games_moves = ""
            game_datetime = datetime.min
            for n in nicknames:
                lichess_game = chess.pgn.read_game(StringIO(lichess.api.user_games(n, max=2, format=SINGLE_PGN)))
                dt = datetime.strptime(re.search(r'\[UTCDate "(.*?)"\]', str(lichess_game)).group(1) + " "
                                              + re.search(r'\[UTCTime "(.*?)"\]', str(lichess_game)).group(1), "%Y.%m.%d %H:%M:%S")
                if (game_datetime < dt):
                    game_datetime = dt
                    game_nickname = n
                print(datetime.now().strftime(
                    "%m.%d %H:%M:%S") + " >>> " + (dt.replace(tzinfo=timezone.utc).astimezone(tz=None).strftime( "%Y.%m.%d %H:%M:%S") + " " + n))
            lichess_game = chess.pgn.read_game(StringIO(lichess.api.user_games(game_nickname, max=2, format=SINGLE_PGN)))
            last_game = str(lichess_game).splitlines()[1]
            if last_game == procesed_game:
                continue
            bot.send_message(message.chat.id, "___________________________________________")
            index = str(lichess_game).index("White")
            isColorWhite = True if str(lichess_game)[index + 7:index + 7 + len(game_nickname)] == game_nickname else False
            link = "lichess.org/study/" + StudyID + "/" + (ChapterWhiteId if isColorWhite else ChapterBlackId)
            bot.send_message(message.chat.id, "White" if isColorWhite else "Black" + " " + game_nickname + " " + str(game_datetime))
            theory_node = chess.pgn.read_game(StringIO( WhiteTheory if isColorWhite else BlackTheory ))
            game_node = lichess_game.variations[0]
            positionMoves = GetMovesByFEN(lichess_game.board().board_fen())
            FromPosition = True if positionMoves is not None else False
            curNode = positionMoves if positionMoves is not None else game_node
            after_comment = False
            while 1:
                moveCount += 1
                moveNotation = str(curNode.parent.board().san(curNode.move))
                games_moves = games_moves + '<b>'
                if (moveCount % 2 == 1 or games_moves == ""):
                    games_moves = games_moves + '\n' + moveWithDot(moveCount) + " "
                else:
                    if after_comment:
                        games_moves = games_moves + 15 * ' '
                        after_comment = False
                    else:
                        games_moves = games_moves + (7 - len(PrevMove)) * ' '
                games_moves = games_moves + moveNotation + '</b>'
                Found = False
                if len(theory_node.variations) == 0:
                    SendMessageToBot(bot, message.chat.id, games_moves, isColorWhite, curNode,
                        "There is no answer in PGN for my " + moveWithDot(moveCount) + str(curNode.parent.board().san(curNode.move) + "\n" + link))
                    break
                for var in theory_node.variations:
                    if curNode.move == var.move:
                        Found = True
                        theory_node = var
                        if len(theory_node.comment) != 0 and theory_node.comment[0] == '.':
                            comment = theory_node.comment[theory_node.comment.index(".\n") + 1:theory_node.comment.index("\n.")]
                            if comment[1:7] == '!trans': # Transposition
                                trans_moves = comment.splitlines()[2]
                                theory_node = chess.pgn.read_game(StringIO( WhiteTheory if isColorWhite else BlackTheory))
                                trans_moves = trans_moves.split()
                                for tm in trans_moves:
                                    for tn in theory_node.variations:
                                        if tm == str(tn.move):
                                            theory_node = tn
                                            break
                                bot.send_message(message.chat.id,'<b>' + 'transposition:' + comment.splitlines()[2] + '</b>', parse_mode='HTML')
                            games_moves = games_moves + comment
                            if moveCount % 2 == 1:
                                games_moves = games_moves + '\n'
                            after_comment = True
                        break
                if Found is False:
                    if (moveCount % 2 == 0 and isColorWhite) or (moveCount % 2 == 1 and not isColorWhite) :
                        SendMessageToBot(bot, message.chat.id, games_moves, isColorWhite, curNode,
                            "There is no answer in PGN for opponent's " + moveWithDot(moveCount) + moveNotation +  "\n" +  link)
                        break
                    SendMessageToBot(bot, message.chat.id, games_moves, isColorWhite, curNode,
                        moveWithDot(moveCount) + moveNotation + " is wrong move " + str(theory_node.board().san(theory_node.variations[0].move)) + " is right one" + "\n" + link)
                    break
                PrevMove = moveNotation
                if FromPosition and len(curNode.variations) == 0:
                    curNode = game_node
                    FromPosition = False
                else:
                    curNode = curNode.variations[0]
            procesed_game = last_game
        except Exception as err:
            print(f"Unexpected {err=}, {type(err)=}")
bot.polling(none_stop=True)