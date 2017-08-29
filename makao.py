from pytalk.utils import *
from itertools import product
import os
import time
import random


class Card:
    ANY = '*'

    CLUB = '\u2663'
    DIAMOND = '\u2666'
    HEART = '\u2665'
    SPADE = '\u2660'
    SUITS = [CLUB, DIAMOND, HEART, SPADE]

    A = 11
    J = 12
    Q = 13
    K = 14
    RANKS = [x for x in range(2, 15)]

    @staticmethod
    def suit_colour(suit):
        return colour(ORANGE) if suit == Card.CLUB or suit == Card.SPADE else colour(RED)

    def __init__(self, rank, suit):
        self.__rank = rank
        self.__suit = suit

    @property
    def rank(self):
        return self.__rank

    @property
    def suit(self):
        return self.__suit

    def __str__(self):
        rank_str = 'AJQK'[self.rank - 11] if self.rank >= 11 else str(self.rank)
        return f'{Card.suit_colour(self.suit)}{rank_str}{self.suit}{default}'


@irc_module
class Makao:

    ranking = {}

    def __init__(self):
        self.deck = [Card(rank, suit) for rank, suit in product(Card.RANKS, Card.SUITS)]
        self.stack = []

        self.turn = 0
        self.playing = False
        self.current_player = None

        self.players = []
        self.player_cards = {}

        self.stay_turns = {}
        self.penalty = 0

        self.suit_requested = None

        Makao.read_ranking()

    @staticmethod
    def read_ranking():
        if Makao.ranking or not os.path.exists('makao.log'):
            return
        with open('makao.log', 'r') as file:
            for line in file:
                player, score = line.split()
                Makao.ranking[player] = int(score)

    @on('\.(?:j|join)$')
    def join(self, user, message):
        if self.playing:
            self.notice(user, 'A Makao game is already ongoing. Please wait until a new Makao game can begin.')
            return
        if user in self.players:
            self.notice(user, "Stay calm. You've already joined this Makao game.")
            return

        self.players.append(user)
        self.player_cards[user] = []
        self.stay_turns[user] = 0
        self.broadcast(user, 'joined the Makao game!')
        time.sleep(1)

    @on('\.leave$')
    def leave(self, user, message):
        if user not in self.players:
            self.notice(user, "You can't leave something you're not part of.")
            return
        if self.playing:
            self.notice(user, 'You have to finish this Makao game.')
            return

        self.players.remove(user)
        self.player_cards.pop(user)
        self.broadcast(user, "left the Makao game :'(")
        time.sleep(1)

    @on('\.start$')
    def start(self, user, message):
        if self.playing:
            self.notice(user, 'A Makao game is already ongoing.')
            return
        if len(self.players) < 2:
            self.broadcast(f'{user}: Sorry, at least 2 players are required to start.')
            return

        self.playing = True
        self.current_player = self.players[0]
        random.shuffle(self.deck)

        for player in self.players:
            self.draw(player, 5)

        while True:
            self.stack.extend([self.deck.pop()])
            if self.stack[-1].rank > 4 and self.stack[-1].rank != 7 and self.stack[-1].rank != Card.A:
                break

        self.broadcast(f"The game of Makao begins! Player order is: {', '.join(self.players)}.")

        self.broadcast(f'Top card is: {self.stack[-1]}')
        time.sleep(1)

    def stop_game(self):
        with open('makao.log', 'w') as file:
            for player, score in Makao.ranking.items():
                file.write(f'{player} {score}\n')
        self.__init__()
        time.sleep(3)

    def draw(self, user, amount=1):
        for x in range(amount):
            self.player_cards[user].extend([self.deck.pop()])
            if not self.deck:
                self.deck = self.stack[:-1][::-1]
                self.stack = [self.stack[-1]]
        self.show_cards(user)

    @on('\.(?:re|remind|cards)$')
    def show_cards(self, user, remind=False):
        if not self.playing:
            return
        if user not in self.players:
            return

        if remind:
            card = self.stack[-1]

            if self.penalty:
                self.notice(user, f"Top card is: {card}. "
                                  f"Penalty sums to {self.penalty} {'cards' if card.rank <= 3 else 'turn(s)'}!")
            else:
                if card.rank <= 4 or self.suit_requested == Card.ANY:
                    self.notice(user, f'Any card(s) may be placed.')
                elif card.rank == Card.A:
                    self.notice(user, f'Suit type: {Card.suit_colour(self.suit_requested)}'
                                      f'{self.suit_requested} is requested.')
                else:
                    self.notice(user, f'Top card is: {card}')

        deck_str = [f'{index + 1}[{card}]' for index, card in self.player_cards[user]]
        self.notice(user, f"Your cards are:  {'  '.join(deck_str)}")

    @on('\.(?:p|play|place) [\d ]+$')
    def place(self, user, message):
        if not self.playing:
            return
        if user not in self.players:
            self.notice(user, "You are not part of this Makao game.")
            return
        if self.current_player != user:
            self.notice(user, f"It's {self.players[self.turn]}'s turn, please wait.")
            return
        if self.stack[-1].rank == Card.A and not self.suit_requested:
            self.notice(user, "You have to select a suit!")
            return

        # Check if indexes are correct
        indexes = []
        for x in message.split()[1:]:
            x = int(x) - 1
            if x > len(self.player_cards[user]) - 1 or x in indexes:
                self.notice(user, "Invalid place!")
                return
            indexes.append(x)

        # Check if it's a correct card placement
        cards = [self.player_cards[user][x] for x in indexes]
        if not self.valid_placement(cards):
            self.notice(user, "Invalid place!")
            return

        # Resets
        if self.suit_requested:
            self.suit_requested = None

        # Assigning penalty points
        if cards[-1].rank == 7:
            self.penalty = 0
        if cards[0].rank <= 4:
            if not self.penalty:
                self.penalty = 0
            if cards[0].rank == 4:
                self.penalty += len(cards)
            else:
                for card in cards:
                    self.penalty += card.rank

        # Constructing the message
        place_msg = f"Last card{'s' if len(cards) > 1 else ''} placed:"
        for card in cards:
            self.stack.extend([card])
            place_msg += f'  {card}'
            self.player_cards[user].remove(card)

        # Append penalty notification if necessary
        if self.penalty:
            place_msg += f"  -  Penalty sums to {self.penalty} {'cards' if card.rank < 4 else 'turn(s)'}!"

        # Broadcasting the placement
        self.broadcast(place_msg)

        # Checking for Makao
        if len(self.player_cards[user]) == 1:
            self.broadcast(f"{colour(RED)}Makao!{default} {user} has only 1 card left!")
        elif not self.player_cards[user]:
            self.make_winner(user)
            # Check if game ended
            if not self.playing:
                return

        # If an user placed an Ace they have to change the suit first
        if self.stack[-1].rank == Card.A:
            return

        self.next_turn()

    def valid_placement(self, cards):
        start_card = cards[0]
        stack_card = self.stack[-1]

        def same_rank():
            for card in cards:
                if card.rank != start_card.rank:
                    return False
            return True

        # Special conditions
        if self.penalty:
            # 7s are used as a stop cards
            if start_card.rank == 7:
                return same_rank()

            # When there's a 2 / 3 on stack only a 2 / 3 can be placed
            if stack_card.rank <= 3 < start_card.rank:
                return False

            # When there's a 4 on the stack only a 4 can be placed
            if stack_card.rank == 4 and start_card.rank != 4:
                return False

        else:
            # Check if any card can be placed
            if stack_card.rank <= 4 or self.suit_requested == Card.ANY:
                return same_rank()

            # Aces can be placed over anything
            if start_card.rank == Card.A:
                return same_rank()

            # Check if a specific card suit should be placed
            if self.suit_requested:
                if start_card.suit != self.suit_requested:
                    return False
                return same_rank()

        # Default check
        if start_card.rank != stack_card.rank and start_card.suit != stack_card.suit:
            return False
        return same_rank()

    def make_winner(self, user):
        self.turn -= 1
        self.players.remove(user)
        self.broadcast(f"{colour(RED)}Makao!{default} {user} finished!")

        if user not in Makao.ranking:
            Makao.ranking[user] = 0
        Makao.ranking[user] += len(self.players)

        if len(self.players) == 1:
            self.broadcast(f"And thus the Makao game as well...")
            self.stop_game()
            return

    @on('\.(?:c|change)')
    def change_suit(self, user, message):
        if not self.playing:
            return
        if self.current_player != user or self.stack[-1].rank != Card.A:
            self.notice(user, "You can't change the suit!")
            return

        if 'club' in message:
            self.suit_requested = Card.CLUB
        elif 'diamond' in message:
            self.suit_requested = Card.DIAMOND
        elif 'heart' in message:
            self.suit_requested = Card.HEART
        elif 'spade' in message:
            self.suit_requested = Card.SPADE
        elif 'any' in message:
            self.suit_requested = Card.ANY
        else:
            self.notice(user, "Invalid suit!")
            return

        if self.suit_requested == Card.ANY:
            self.broadcast(f'{user} is an indulgent god. The next player can start with any card!')
        else:
            self.broadcast(f'Suit requested:  {Card.suit_colour(self.suit_requested)}{self.suit_requested}')
        self.next_turn()

    @on('\.(?:pa|pass|d|draw|resign|surrender|forfeit)$')
    def resign(self, user, message):
        if not self.playing:
            return
        if user not in self.players:
            self.notice(user, "You are not part of this Makao game.")
            return
        if self.current_player != user:
            self.notice(user, f"It's {self.current_player}'s turn, please wait.")
            return

        if self.penalty:
            if self.stack[-1].rank <= 3:
                self.draw(user, self.penalty)
                self.broadcast(f"{user} had to draw {self.penalty} cards :'(")
            else:
                self.stay_turns[user] = self.penalty
                self.broadcast(f"{user} will have to stay away for {self.penalty} turn"
                               f"{'s' if self.penalty > 1 else ''} :'(")
            self.penalty = 0
        else:
            self.draw(user)

        self.next_turn(remind=True)

    @on('\.(?:turn|who)$')
    def who_now(self, user, message):
        if not self.playing:
            if self.players:
                self.notice(user, f"{', '.join(self.players)} joined the game.")
            else:
                self.notice(user, "There's no running Makao game.")
            return
        self.notice(user, f"Currently playing {', '.join(self.players)}. {self.current_player} has to do the move.")

    def next_turn(self, remind=False):
        while True:
            self.turn += 1
            self.turn %= len(self.players)
            self.current_player = self.players[self.turn]
            if self.stay_turns[self.current_player] == 0:
                break
            else:
                self.stay_turns[self.current_player] -= 1

        self.notice(self.current_player, f"It's your turn {self.current_player}")
        self.show_cards(self.current_player, remind=remind)

    @on('\.(?:rank|score|stats|leader)')
    def leader_board(self, user, message):
        if not Makao.ranking or len(Makao.ranking) < 3:
            self.broadcast('Not available.')
            time.sleep(1)
            return
        if self.playing:
            self.broadcast('Please wait until this game finishes.')
            time.sleep(1)
            return

        args = message.split()
        if len(args) > 1:
            if not args[1] in Makao.ranking:
                self.broadcast(f'Could not find user {args[1]}.')
            else:
                self.broadcast(f'{args[1]} has {Makao.ranking[args[1]]} points.')
            time.sleep(1)
            return

        top = sorted(Makao.ranking.items(), key=lambda x: x[1])
        top_str = f'1st {top[-1][0]}({top[-1][1]} points), '
        top_str += f'2nd {top[-2][0]} ({top[-2][1]} points), '
        top_str += f'3rd {top[-3][0]} ({top[-3][1]} points)'
        self.broadcast(top_str)
        time.sleep(1)

    @on('\.override')
    def override(self, user, message):
        if user != 'Zumza':
            self.notice(user, "This command can be used only by the game master(Zumza).")
            return
        try:
            eval(message.split('.override')[1])
        except Exception as error:
            self.broadcast('>', type(error).__name__)
