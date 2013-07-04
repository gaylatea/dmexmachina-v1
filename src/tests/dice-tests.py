# -*- coding: utf-8 -*-
"""Unit tests for the frontpage DM Ex Machina pages.


This is free and unencumbered software released into the public domain.

Anyone is free to copy, modify, publish, use, compile, sell, or
distribute this software, either in source code form or as a compiled
binary, for any purpose, commercial or non-commercial, and by any
means.

In jurisdictions that recognize copyright laws, the author or authors
of this software dedicate any and all copyright interest in the
software to the public domain. We make this dedication for the benefit
of the public at large and to the detriment of our heirs and
successors. We intend this dedication to be an overt act of
relinquishment in perpetuity of all present and future rights to this
software under copyright law.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.

For more information, please refer to <http://unlicense.org/>

"""
##
from unittest import TestCase
from dmxm import dice


##
class DMXMDiceTests(TestCase):
    """Tests for the dice roller functionality."""

    def test_dice_parser(self):
        """Tests that '1d20+4' can evaluate properly."""
        dres = dice.parse('1d20+4')
        self.assertEqual(dres, (1, 20, 4, 0))

    def test_dice_parser_incorrect(self):
        """Tests that improper expressions just return None."""
        dres = dice.parse('1x100')
        self.assertEqual(dres, None)

    def test_dice_parser_no_addend(self):
        """Don't require a '+X' at the end."""
        dres = dice.parse('5d20')
        self.assertEqual(dres, (5, 20, 0, 0))

    def test_dice_parser_no_multiplicand(self):
        """Don't require a 'X' in from of 'dY'."""
        dres = dice.parse('d10')
        self.assertEqual(dres, (1, 10, 0, 0))

    def test_dice_pullout(self):
        """Dice rolls can occur multiple times in posts."""
        post = 'Basic Melee Attack, 1d20+3, Damage d10+4'
        rolls = dice.pullout(post)

        self.assertEqual(rolls, [(1, 20, 3, 0), (1, 10, 4, 0)])

    def test_dice_pullout_nodice(self):
        """Dice rolls may not appear in posts."""
        post = 'This is a test post with no die rolls.'
        rolls = dice.pullout(post)

        self.assertEqual(rolls, [])

    def test_dice_roll(self):
        """Hard to test, but make sure that the range is correct."""
        scheme = (2, 20, 4, 0)
        roll = dice.roll(scheme)

        self.assertEqual(True, (roll <= 44))
        self.assertEqual(True, (roll >= 6))

    def test_dice_brutal(self):
        """Some weapons support 'brutal' re-rolling of low damage.

        To prevent people being lame-asses (even though I trust my
        players to a certain extent), this does not support brutal
        damage on d20 rolls.

        """
        dres = dice.parse('d10+5b2')
        self.assertEqual(dres, (1, 10, 5, 2))

        roll = dice.roll(dres)
        # The 'Brutal 2' should prevent anything less than 8.
        self.assertEqual(True, (roll >= 8))
