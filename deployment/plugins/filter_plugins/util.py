class FilterModule(object):
    def filters(self):
        return {"mkcron": mkcron}

def mkcron(times_per_day, start_hour=0):
    if 24 % times_per_day != 0:
        raise ValueError('Number of times per day must divide 24')
    if times_per_day == 1:
        return '*-*-* {}:00:00'.format(start_hour)
    else:
        period = 24 // times_per_day
        start_hour %= period
        return '*-*-* {}/{}:00:00'.format(start_hour, period)
