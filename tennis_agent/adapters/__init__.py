from .cintoia import Cintoia
from .esport import Esport
from .playfi import PlayFi


def sources():
    return [Cintoia("Rosegarden", "rosegarden.cintoia.com", "rosegarden-PIYZk2Bv", "tennis"),
            Cintoia("Tapiolan Tennispuisto", "tennispuisto.cintoia.com", "tennispuisto-rTVILEOT", "sisätennis"),
            Esport(),
            Cintoia("Targa Arena", "targaarena.cintoia.com", "kauniaistenurheilupuisto-9WQB1q2Z", "tennis"),
            PlayFi()]
