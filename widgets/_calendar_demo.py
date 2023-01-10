'''
    Demonstration Calendar interface for 'Calendar' widget
'''
import logging

wName = 'Calendar'

class Demo:

    def __init__(self, cfg):
        self.name   = __name__
        self.logger = logging.getLogger(self.name)

        self.sample_list = [
            {'start': None, 'time': '19:00', 'days_ahead': 0, 'all_day': False, 'summary': 'Eat'},
            {'start': None, 'time': '23:00', 'days_ahead': 0, 'all_day': False, 'summary': 'Sleep'},
            {'start': None, 'time': '00:00', 'days_ahead': 1, 'all_day': True, 'summary': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.'},
            {'start': None, 'time': '13:37', 'days_ahead': 2, 'all_day': False, 'summary': 'Repeat'}
        ]

        

    def get_calendar_items(self, dt, days_ahead):
        '''
            Return upcoming calendar items in a neat list, sorted by start date

            Format of a single item:
                {
                'start': [datetime],
                'time': [string, 'hh:mm'],
                'days_ahead': [int],
                'all_day': [bool],
                'summary': [string]
                }
        '''

        return self.sample_list
