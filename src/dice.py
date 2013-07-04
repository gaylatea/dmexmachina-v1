# -*- coding: utf-8 -*-
"""Dice roller parser for DM Ex Machina.

Allows players to use 'XdY+Z' notation for dice rolls.

"""
##
import random
import re
import time

##
DIEROLL = re.compile('([0-9]*)d([0-9]+)(\+[0-9]+)*(b[0-9]+)*')

##
def parse(expr):
	"""Returns a list of integers for the dice roller."""
	dexp = DIEROLL.match(expr)

	if not dexp or not dexp.group(2):
		return None

	muliplicand = 1 if not dexp.group(1) else int(dexp.group(1))
	dietype = int(dexp.group(2))
	addend = 0 if not dexp.group(3) else int(dexp.group(3))
	brutal = 0 if not dexp.group(4) else int(dexp.group(4)[1:])

	return (muliplicand, dietype, addend, brutal)


def pullout(post):
	"""Pulls out dice rolls from a post for later parsing."""
	rolls = DIEROLL.findall(post)
	ret = []
	for each in rolls:
		i_mult = 1 if not each[0] else int(each[0])
		i_dietype = int(each[1])
		i_addend = 0 if not each[2] else int(each[2])
		i_brutal = 0 if not each[3] else int(each[3][1:])
		item = (i_mult, i_dietype, i_addend, i_brutal)

		ret.append(item)

	return ret


def roll(schema):
	"""Rolls the dice and returns a result."""
	# Reseed the random generator each time a new die is rolled.
	random.seed(time.ctime())

	sums = 0
	for i in xrange(1, schema[0]+1):
		result = 0
		while result <= schema[3]:
			result = random.randint(1, schema[1])
		sums += result

	sums += schema[2]

	return sums


def process(post):
	"""Rolls and replaces instances of dice rolls with results."""
	rolls = pullout(post)
	if rolls:
		for r in rolls:
			result = roll(r)
			thisroll = re.compile('(%d)*d(%d)(\+%d)*(b%d)*' % r)
			post = thisroll.sub(str(result), post, 1)

	return post
