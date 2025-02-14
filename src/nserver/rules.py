# pylint: disable=too-few-public-methods

### IMPORTS
### ============================================================================
## Standard Library
import re
from typing import Any, Callable, List, Optional, Pattern

## Installed
import tldextract

## Application
from .models import Query

### CLASSES
### ============================================================================
ResponseFunction = Callable[[Query], Any]  # Note: change Any to Union later


class RuleBase:
    """Base class for all Rules to inherit from."""

    def get_func(self, query: Query) -> Optional[ResponseFunction]:
        """From the given query return the function to run, if any.

        If no function should be run (i.e. because it does not match the rule),
        then return None.

        This is to allow more efficient methods when determining a match and
        getting the rule function may be expensive (e.g. blueprints).
        """
        raise NotImplementedError()


class RegexRule(RuleBase):
    """Rule that uses the provided regex to attempt to match the query name.

    When operating with `case_sensitive=False`, the query name is converted to
    lowercase prior to matching. The regex must expect that the queries will all
    be lowercased (i.e. the regex is NOT automatically converted).
    """

    def __init__(
        self,
        regex: Pattern,
        allowed_qtypes: List,
        func: ResponseFunction,
        case_sensitive: bool = False,
    ) -> None:
        # TODO: Consider allowing strings and then compiling to regex since can
        # test for regex types: `if isinsance(regex, Pattern)`

        self.regex = regex  # TODO: find way to make regex "lowercase"
        self.allowed_qtypes = set(allowed_qtypes)
        self.func = func
        self.case_sensitive = case_sensitive
        return

    def get_func(self, query):
        if query.type not in self.allowed_qtypes:
            return None

        query_name = query.name if self.case_sensitive else query.name.lower()

        if self.regex.fullmatch(query_name):
            return self.func
        return None

    def __repr__(self):
        return f"{self.__class__.__name__}(regex={self.regex.pattern!r}, allowed_qtypes={self.allowed_qtypes!r}, func={self.func!r})"

    def __str__(self):
        return f"{self.__class__.__name__}({self.regex.pattern!r}, {self.allowed_qtypes!r})"


class WildcardStringRule(RuleBase):
    """Rule that allows a more concise way of matching query names.

    Examples:
        _dmarc.{base_domain}
        *._dkim.**
        foo.*.bar.com

    When operating with `case_sensitive=False`, both the wildcard string and the
    query name are covereted to lowercase prior to matching.
    """

    def __init__(
        self,
        wildcard_string: str,
        allowed_qtypes: List,
        func: ResponseFunction,
        case_sensitive: bool = False,
    ) -> None:
        self.wildcard_string = wildcard_string if case_sensitive else wildcard_string.lower()
        self.allowed_qtypes = allowed_qtypes
        self.func = func
        self.case_sensitive = case_sensitive
        return

    def get_func(self, query):
        if query.type not in self.allowed_qtypes:
            return None

        query_name = query.name if self.case_sensitive else query.name.lower()

        regex = self._get_regex(query_name)
        if regex.fullmatch(query_name):
            return self.func
        return None

    def _get_regex(self, query_domain):
        """Given a query domain, produce the regex used for matching.

        A seperate function to make testing easier.
        """
        sub_vars = {}

        domain_parts = tldextract.extract(query_domain)
        if domain_parts.suffix:
            # Public domain
            sub_vars["base_domain"] = domain_parts.registered_domain
        else:
            # Internal / fake domain
            sub_vars["base_domain"] = domain_parts.domain

        regex_parts = []
        for part in self.wildcard_string.format(**sub_vars).split("."):
            if part == "*":
                # Single part match
                if self.case_sensitive:
                    regex_parts.append(r"[a-zA-Z0-9\-\_]+")
                else:
                    regex_parts.append(r"[a-z0-9\-\_]+")
            elif part == "**":
                # Extended part match
                if self.case_sensitive:
                    regex_parts.append(r"(?:[a-zA-Z0-9\-\_]+\.)*(?:[a-zA-Z0-9\-\_]+)")
                else:
                    regex_parts.append(r"(?:[a-z0-9\-\_]+\.)*(?:[a-z0-9\-\_]+)")
            else:
                regex_parts.append(re.escape(part))

        regex = re.compile(r"\.".join(regex_parts))
        return regex

    def __repr__(self):
        return f"{self.__class__.__name__}(wildcard_string={self.wildcard_string!r}, allowed_qtypes={self.allowed_qtypes!r}, func={self.func!r})"

    def __str__(self):
        return f"{self.__class__.__name__}({self.wildcard_string!r}, {self.allowed_qtypes!r})"
