import json
import operator
import random
import re
from collections import OrderedDict
from hashlib import md5
from uuid import uuid4

from faker import Faker
import string
import datetime
from calendar import isleap

from pganonymize.config import config
from pganonymize.exceptions import InvalidProvider, InvalidProviderArgument, ProviderAlreadyRegistered


class FakerInitializer(object):
    """A wrapper that allows to instantiate a faker instance with specific locales."""

    def __init__(self):
        self._faker = None
        self._options = None

    @property
    def options(self):
        if self._options is None:
            self._options = config.schema.get('options', {}).get('faker', {})
        return self._options

    @property
    def default_locale(self):
        return self.options.get('default_locale')

    @property
    def faker(self):
        """
        Return the actual :class:`faker.Faker` instance, with optional locales taken from the YAML schema.

        :return: A faker instance
        :rtype: faker.Faker
        """
        if self._faker is None:
            locales = self.options.get('locales')
            self._faker = Faker(locales)
        return self._faker

    def get_locale_generator(self, locale):
        """
        Get the internal generator for the given locale.

        :param str locale: A locale string
        :raises InvalidProviderArgument: If locale is unknown (not configured within the global locales option).
        :return: A Generator instance for the given locale
        :rtype: faker.Generator
        """
        try:
            generator = self.faker[locale]
        except KeyError as e:
            raise InvalidProviderArgument(f"Locale \'{locale}\' is unknown. Have you added it to the global option "
                                          f"(" f"options.faker.locales)?") from e

        return generator


faker_initializer = FakerInitializer()


class ProviderRegistry(object):
    """A registry for provider classes."""

    def __init__(self):
        self._registry = OrderedDict()

    def register(self, provider_class, provider_id):
        """
        Register a provider class.

        :param pganonymize.providers.Provider provider_class: Provider class that should be registered
        :param str provider_id: A string id to register the provider for
        :raises ProviderAlreadyRegistered: If another provider with the given id has been registered
        """
        if provider_id in self._registry:
            raise ProviderAlreadyRegistered(f'A provider with the id "{provider_id}" has already been registered')

        self._registry[provider_id] = provider_class

    def get_provider(self, provider_id):
        """
        Return a provider by its provider id.

        :param str provider_id: The string id of the desired provider.
        :raises InvalidProvider: If no provider can be found with the given id.
        :return: The provider class that matches the id.
        :rtype: type
        """
        for key, cls in self._registry.items():
            if (cls.regex_match is True and re.match(re.compile(key), provider_id) is not None) or key == provider_id:
                return cls
        raise InvalidProvider(f'Could not find provider with id "{provider_id}"')

    @property
    def providers(self):
        """
        Return the registered providers.

        :rtype: OrderedDict
        """
        return self._registry


provider_registry = ProviderRegistry()


def register(provider_id, **kwargs):
    """
    A wrapper that registers a provider class to the provider registry.

    :param str provider_id: The string id to register the provider for.
    :keyword registry: The registry the provider class is registered at (default is the `provider_registry` instance).
    :return: The decorator function
    :rtype: function
    """

    def wrapper(provider_class):
        registry = kwargs.get('registry', provider_registry)
        registry.register(provider_class, provider_id)
        return provider_class

    return wrapper


class Provider(object):
    """Base class for all providers."""

    regex_match = False
    """Defines whether a provider matches it's id using regular expressions."""

    @classmethod
    def alter_value(cls, original_value, **kwargs):
        """
        Alter or replace the original value of the database column.

        :param original_value: The original value of the database column.
        """
        raise NotImplementedError()


@register('choice')
class ChoiceProvider(Provider):
    """Provider that returns a random value from a list of choices."""

    @classmethod
    def alter_value(cls, original_value, **kwargs):
        return random.choice(kwargs.get('values'))


@register('clear')
class ClearProvider(Provider):
    """Provider to set a field value to None."""

    @classmethod
    def alter_value(cls, original_value, **kwargs):
        return None


@register('fake.+')
class FakeProvider(Provider):
    """Provider to generate fake data."""

    regex_match = True

    @classmethod
    def alter_value(cls, original_value, **kwargs):
        func_name = kwargs['name'].split('.', 1)[1]
        func_kwargs = kwargs.get('kwargs', {})
        locale = kwargs.get('locale', faker_initializer.default_locale)
        # Use the generator for the locale if a locale is configured (per field definition or as global default locale)
        faker_generator = faker_initializer.get_locale_generator(locale) if locale else faker_initializer.faker
        try:
            func = operator.attrgetter(func_name)(faker_generator)
        except AttributeError as exc:
            raise InvalidProviderArgument(exc) from exc
        return func(**func_kwargs)


@register('mask')
class MaskProvider(Provider):
    """Provider that masks the original value."""

    default_sign = 'X'
    """The default string used to replace each character."""

    @classmethod
    def alter_value(cls, original_value, **kwargs):
        sign = kwargs.get('sign', cls.default_sign) or cls.default_sign
        return sign * len(original_value)


@register('partial_mask')
class PartialMaskProvider(Provider):
    """Provider that masks some of the original value."""

    default_sign = 'X'
    default_unmasked_left = 1
    default_unmasked_right = 1
    """The default string used to replace each character."""

    @classmethod
    def alter_value(cls, original_value, **kwargs):
        sign = kwargs.get('sign', cls.default_sign) or cls.default_sign
        unmasked_left = kwargs.get('unmasked_left', cls.default_unmasked_left) or cls.default_unmasked_left
        unmasked_right = kwargs.get('unmasked_right', cls.default_unmasked_right) or cls.default_unmasked_right

        return (
            original_value[:unmasked_left] +
            (len(original_value) - (unmasked_left + unmasked_right)) * sign +
            original_value[-unmasked_right:]
        )


@register('md5')
class MD5Provider(Provider):
    """Provider to hash a value with the md5 algorithm."""

    default_max_length = 8
    """The default length used for the number representation."""

    @classmethod
    def alter_value(cls, original_value, **kwargs):
        as_number = kwargs.get('as_number', False)
        as_number_length = kwargs.get('as_number_length', cls.default_max_length)
        hashed = md5(original_value.encode('utf-8')).hexdigest()
        return int(hashed, 16) % (10 ** as_number_length) if as_number else hashed


@register('set')
class SetProvider(Provider):
    """Provider to set a static value."""

    @classmethod
    def alter_value(cls, original_value, **kwargs):
        return kwargs.get('value')


@register('uuid4')
class UUID4Provider(Provider):
    """Provider to set a random uuid value."""

    @classmethod
    def alter_value(cls, original_value, **kwargs):
        return uuid4()


@register('fiscalcode')
class FiscalCodeProvider(Provider):
    """Provider to hash a fiscal code."""

    @classmethod
    def alter_value(cls, original_value, **kwargs):
        crypt_fiscal_code = md5(original_value.encode('utf-8')).hexdigest()

        def check_day(n_day):
            if int(n_day[3]) > 7:
                n_day[3] = str(1)
            return n_day[3:5]

        def check_month(month_character):
            char_month = ['A', 'B', 'C', 'D', 'E', 'H', 'L', 'M', 'P', 'R', 'S', 'T']
            if month_character in char_month:
                return month_character
            index = 4
            return char_month[index]

        def generate_fiscal_code(fc_characters, fc_numbers):
            separator = ''
            generate_fiscal_code = ((separator.join(fc_characters[:6]) + separator.join(fc_numbers[:2]) +
                                     check_month(fc_characters[8])) + separator.join(check_day(fc_numbers)) +
                                    fc_characters[11]) + separator.join(fc_numbers[6:9]) + fc_characters[12]

            return generate_fiscal_code

        split_string = []
        n = 2
        for index in range(0, len(crypt_fiscal_code), n):
            split_string.append(crypt_fiscal_code[index: index + n])

        characters = []

        for digit in split_string:
            digit_hex = int(digit, 16)
            digit_char = digit_hex % 26
            character = chr(ord('A') + digit_char)
            characters.append(character)

        numbers = []
        for digit in split_string[6:]:
            digit_hex = int(digit, 16)
            digit_char = digit_hex % 10
            numbers.append(str(digit_char))

        generate_fiscal_code = generate_fiscal_code(characters, numbers)
        return generate_fiscal_code


@register('vatnumber')
class VatNumberProvider(Provider):
    """Provider to hash a vat number."""

    @classmethod
    def alter_value(cls, original_value, **kwargs):
        vatnumber = original_value[2:]
        crypt_vat_number = md5(vatnumber.encode('utf-8')).hexdigest()

        n = 2
        split_string = [crypt_vat_number[index: index + n] for index in range(0, len(crypt_vat_number), n)]

        numbers = [str(int(digit, 16) % 10) for digit in split_string]
        separator = ''
        return f'IT{separator.join(numbers[:9])}'


@register('fiscalcodebusiness')
class FiscalCodeBusinessProvider(Provider):
    """Provider to hash a vat number."""

    @classmethod
    def alter_value(cls, original_value, **kwargs):
        fiscalcode_business = original_value[:]
        crypt_fiscalcode_business = md5(fiscalcode_business.encode('utf-8')).hexdigest()

        n = 2
        split_string = [crypt_fiscalcode_business[index: index + n]
                        for index in range(0, len(crypt_fiscalcode_business), n)]

        numbers = [str(int(digit, 16) % 10) for digit in split_string]
        separator = ''
        return separator.join(numbers[:9])


@register('fiscalcodevat')
class FiscalCodeVatNumberProvider(Provider):
    """Provider to hash a vat number."""

    @classmethod
    def alter_value(cls, original_value, **kwargs):

        if original_value[0].isdigit():
            # code for fiscalcode legal entity
            fiscalcode_business = original_value[:]
            crypt_fiscalcode_business = md5(fiscalcode_business.encode('utf-8')).hexdigest()

            split_string = []
            n = 2
            for index in range(0, len(crypt_fiscalcode_business), n):
                split_string.append(crypt_fiscalcode_business[index: index + n])

            numbers = []
            for digit in split_string:
                digit_hex = int(digit, 16)
                digit_char = digit_hex % 10
                numbers.append(str(digit_char))

            separator = ''
            generate_fiscalcode_business = separator.join(numbers[:9])
            return generate_fiscalcode_business
        else:
            # code for fiscalcode natural person
            crypt_fiscal_code = md5(original_value.encode('utf-8')).hexdigest()

            def check_day(numbers):
                if int(numbers[3]) > 7:
                    numbers[3] = str(1)
                return numbers[3:5]

            def check_month(character):
                char_month = ['A', 'B', 'C', 'D', 'E', 'H', 'L', 'M', 'P', 'R', 'S', 'T']
                if character in char_month:
                    return character
                index = 4
                return char_month[index]

            def generate_fiscal_code(characters, numbers):
                sep = ''
                fiscal_code = f"{sep.join(characters[:6])}" \
                              f"{sep.join(numbers[:2])}" \
                              f"{check_month(characters[8])}" \
                              f"{sep.join(check_day(numbers))}" \
                              f"{characters[11]}" \
                              f"{sep.join(numbers[6:9])}" \
                              f"{characters[12]}"
                return fiscal_code

            split_string = []
            n = 2
            for index in range(0, len(crypt_fiscal_code), n):
                split_string.append(crypt_fiscal_code[index: index + n])

            characters = []

            for digit in split_string:
                digit_hex = int(digit, 16)
                digit_char = digit_hex % 26
                character = chr(ord('A') + digit_char)
                characters.append(character)

            numbers = []
            for digit in split_string[6:]:
                digit_hex = int(digit, 16)
                digit_char = digit_hex % 10
                numbers.append(str(digit_char))

            generate_fiscal_code = generate_fiscal_code(characters, numbers)
            return generate_fiscal_code


@register('phonenumberita')
class PhoneNumberItaProvider(Provider):
    """Provider to set a random value for phone number."""

    @classmethod
    def alter_value(cls, original_value, **kwargs):
        prefix = '+003'
        return prefix + ''.join([str(random.randint(0, 9)) for _ in range(9)])


@register('randomidcard')
class RandomIDCardProvider(Provider):
    """Provider to set a random value for id card."""

    @classmethod
    def alter_value(cls, original_value, **kwargs):
        chars = ''.join(random.choice(string.ascii_letters).upper() for _ in range(2))
        numbers = ''.join([str(random.randint(0, 9)) for _ in range(7)])
        return chars + numbers


@register('apikey')
class ApiKeyProvider(Provider):
    """Provider to set a random uuid"""

    @classmethod
    def alter_value(cls, original_value, **kwargs):
        return uuid4()


@register('jsonstring')
class JsonStringProvider(Provider):
    """Provider to generate jsonstring"""

    @classmethod
    def alter_value(cls, original_value, **kwargs):
        return json.dumps(kwargs.get('object'))


@register('sameyear')
class SameYearProvider(Provider):
    """Provider to generate a random date but with same year of original value."""

    @classmethod
    def alter_value(cls, original_value, **kwargs):
        if not original_value:
            return None
        birth_date = faker_initializer.faker.date_of_birth()
        # birth_date = datetime.datetime.strptime('1968-02-29', "%Y-%m-%d").date()
        if isleap(birth_date.year):
            birth_date = birth_date.replace(day=random.randint(1, 25))
        year = (
            original_value.year if isinstance(original_value, datetime.date) else
            datetime.datetime.strptime(original_value, "%Y-%m-%d").year
        )
        # print(f"{type(original_value)}, {original_value}, {type(birth_date)}, {birth_date}")
        return birth_date.replace(year=year)
