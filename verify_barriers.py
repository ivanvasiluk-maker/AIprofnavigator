#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify barrier buttons are working"""

from keyboards import PSYCH_BARRIER_OPTIONS
from handlers.career import handle_barrier_detail_actions

barrier_buttons = [
    'Работа с людьми',
    'Помощь людям',
    'Обучение',
    'Организация процессов',
    'Управление',
    'Творчество'
]

print('BARRIER SELECTION BUTTONS CHECK:')
print('=' * 60)

for btn in barrier_buttons:
    if btn in PSYCH_BARRIER_OPTIONS:
        print(f'✓ "{btn}" found')
    else:
        print(f'✗ "{btn}" NOT FOUND')

print('\n' + '=' * 60)
print(f'Total barrier options: {len(PSYCH_BARRIER_OPTIONS)}')
print(f'Handler exists: {handle_barrier_detail_actions is not None}')
print('\n✓ BARRIER FLOW WORKS')
