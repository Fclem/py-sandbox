import ConfigGenerator


def run():
    return ConfigGenerator.ConfigGenerator('ConfigEnvironmentsList')


if __name__ == '__main__':
    a = run()
    a.gen()
