# Coin clicker

![Made with love in Brazil](https://madewithlove.now.sh/br?heart=true&template=for-the-badge)
[![Python](https://forthebadge.com/images/badges/made-with-python.svg)](https://forthebadge.com)

## Screenshot 

![CLI Screenshot](https://github.com/lee-hodg/coin-clicker/blob/master/coin_clicker.png?raw=true)

The purpose of this app is to visit telegram clickbot channels and automatically visit
the websites they provide in order to earn crypto-currency, such as LTC.

## Requirements

Python 3.6+

## Installation

```bash
pip install coin-clicker
```

## Running

```bash
python -m coin_clicker 
```

You will be asked to enter your phone number and then verify the code they send you on
the first run. On future runs you can select from existing numbers.
Next you choose which bot you wish to visit sites for.

You should see the script visiting websites provided and earning crypto for you.
At some point it will run out of websites to visit and wait until more become available.

Ensure to run from a directory in which you have write permissions so
that the session can be stored successfully.

## Developer notes

With `poetry` there is no need to have a `setup.py` in the root. Just run
`poetry build` and `poetry publish`. The archived in `dist/` will get a `setup.py` generated
from the values in `pyproject.toml`.
