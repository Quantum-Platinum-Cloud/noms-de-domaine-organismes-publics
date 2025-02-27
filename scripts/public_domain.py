import csv
from dataclasses import dataclass
from datetime import date
from functools import total_ordering
import logging
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Domains that are commonly found behind redurections but are not public service:
NON_PUBLIC_DOMAINS = {
    "128k.io",
    "3dathome.fr",
    "attichy.com",
    "bellevillesurmeuse.com",  # Domaine squatté
    "catchtiger.com",  # squatte www.villedesaintfrancois.fr
    "changementadresse-carte-grise.com",  # squatte www.roussillo-conflent.fr
    "cloudflaressl.com",
    "commententreprendre.com",  # squatte cma-bourgogne.fr
    "communecter.org",  # Une association
    "creps.ovh",
    "cyberfinder.com",
    "dropcatch.com",  # squatte mairie-clarensac.com
    "esbooks.co.jp",  # squatte pezenes.info
    "eureka27.fr",  # squatte paulhac15.fr
    "gitbook.com",
    "github.com",
    "go.crisp.chat",
    "google.com",
    "host-web.com",
    "imperva.com",
    "incapsula.com",
    "infomaniak.com",
    "medium.com",
    "mesvres.com",  # Domaine squatté
    "microsoftonline.com",
    "milfshorny.com",  # squatte www.opoul.fr et villelefousseret.fr.
    "notes-de-frais.info",  # squatte la mairie de lamotheachard.com
    "opendatasoft.com",
    "ovh.co.uk",
    "passeport-mairie.com",  # squatte www.mairiedeliverdy.fr et www.mairieozon.fr
    "plafond-pinel.info",  # squatte la CC du Lauragais Sud: www.colaursud.fr
    "pre-demande.fr",  # squatte www.ponthevrard-mairie.fr
    "sarbacane.com",
    "sendinblue.com",
    "sioracderiberac.com",
    "varchetta.fr",  # squatte www.commune-la-chapelle-de-brain.fr
    "viteundevis.com",  # squatte mairiemarignaclasclares.fr
    "voxaly.com",
    "wewmanager.com",
}


@total_ordering
@dataclass
class Domain:
    name: str
    source_file: Path = None
    comment: str = ""
    http_status: str | None = None
    https_status: str | None = None
    # http*_status can also starts with "Redirects to: "
    #
    # It's encouraged to add any needed attributes like:
    # smtp_status
    # ssh_status
    # ...

    @classmethod
    def csv_headers(cls):
        return ('name', 'http_status', 'https_status')

    def set_status(self, service, status):
        """Set new status for the given service.

        like: domain.set_status("https", "200 OK")
        """
        if f"{service}_status" not in self.csv_headers():
            raise ValueError(
                f"Can't set status for service {service}: "
                f"{service}_status is not a Domain attribute."
            )
        setattr(self, f"{service}_status", status)

    def astuple(self):
        """Usefull for CSV output."""
        return tuple(getattr(self, attr) for attr in self.csv_headers())

    @classmethod
    def fromtuple(cls, t):
        """Usefull to read from CSV files."""
        attrs = dict(zip(cls.csv_headers(), t))
        return cls(**attrs)

    @classmethod
    def from_file_line(cls, file, line):
        """Creates a Domain instance from a text line.

        The provided line may just be a domain nane, or a full URL.
        """
        domain, comment = line, ""
        if "#" in line:
            domain, comment = line.split("#", maxsplit=1)
        kwargs = {"comment": comment.strip(), "source_file": file}
        domain = domain.strip().lower()
        if domain.startswith("http://") or domain.startswith("https://"):
            return cls.from_url(urlparse(domain), **kwargs)
        return cls(domain, **kwargs)

    @classmethod
    def from_url(cls, url, **kwargs):
        """Constructs a Domain instance from the result of urlparse."""
        if url.scheme == "https":
            return cls(name=url.netloc, https_status="200 OK", **kwargs)
        else:
            return cls(name=url.netloc, http_status="200 OK", **kwargs)

    def is_not_public(self) -> bool:
        """Returns False if the domain is clearly not public (in NON_PUBLIC_DOMAINS)."""
        return any(self.name.endswith(non_public) for non_public in NON_PUBLIC_DOMAINS)

    def __hash__(self):
        return hash(self.name)

    def __lt__(self, other):
        return self.name.split(".")[::-1] < other.name.split(".")[::-1]

    def __repr__(self):
        if self.comment:
            return f"{self.name}  # {self.comment}"
        else:
            return self.name

    def __eq__(self, other):
        if isinstance(other, str):
            return self.name == other
        return self.name == other.name

    @property
    def url(self) -> str:
        """Representation of this domain as an URL."""
        if self.https_status.startswith("200 "):
            return f"https://{self.name}"
        elif self.http_status.startswith("200 "):
            return f"http://{self.name}"
        else:
            raise ValueError(
                "Can't represent Domain as an URL, not sure about the scheme."
            )


def parse_files(*files: Path) -> set[Domain]:
    """Parse one or many files containing lines of domains.

    It allows comments in source files, starting with # anywhere in the line.
    """
    return {
        Domain.from_file_line(file, line)
        for file in files
        for line in file.read_text(encoding="UTF-8").splitlines()
        if not line.startswith("#")
    }


def parse_csv_file(domainsfile):
    domains = set()
    try:
        with open(domainsfile, "r", encoding="UTF-8") as domainsfile:
            domainsreader = csv.reader(domainsfile)
            next(domainsreader)
            for row in domainsreader:
                domains.add(Domain.fromtuple(row))
        return domains
    except FileNotFoundError:
        return set()


def write_csv_file(domainsfile, domains):
    with open(domainsfile, "w", encoding="UTF-8") as f:
        domainswriter = csv.writer(f, lineterminator="\n")
        domainswriter.writerow(Domain.csv_headers())
        for domain in sorted(domains):
            try:
                domainswriter.writerow(domain.astuple())
            except UnicodeEncodeError:
                logger.exception(f"Can't write line in CSV file: {domain.astuple()!r}")
