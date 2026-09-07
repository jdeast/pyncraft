"""Download the 3D models the STL examples use.

The models are not in the repository. Git keeps every version of every file for
ever, and these come to 72 MB, so tracking them charged every clone 72 MB
permanently for files most people never open. They live on a release instead and
are fetched the first time an example needs one.

Nothing here needs installing. Examples call:

    from fetch_models import ensure
    path = ensure("T-Rex.stl")

which returns a path to the file, downloading it into examples/data/ first if it
is missing, and checking its SHA-256 afterwards. Run this file directly to fetch
models by hand:

    python fetch_models.py               # everything
    python fetch_models.py T-Rex.stl     # just one
"""

import hashlib
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

RELEASE_URL = "https://github.com/jdeast/pyncraft/releases/download/models-v1/"

DATA_DIR = Path(__file__).resolve().parent / "data"

# name -> (sha256, size in bytes). Regenerate if the release is ever replaced.
MODELS = {
    "0.stl": ("31e91071093ab68ce3afaeb543685d55f49f923a1d5dfa58513e9eb5529f5b14", 436961),
    "1.stl": ("e43f333d3638ad55625d0a435cf5838db88dd935ca372c9ca1e4b7ba14b8bdae", 10809),
    "2.stl": ("7c9178b4561c065dd1c0ef4f6c9a240b50caf614ea9e763e28c8c234a76060d6", 215244),
    "3.stl": ("8ec0abbc3302a6a305b196fafc1115134301daae013a5d0e518fb09c7f59dad8", 443434),
    "4.stl": ("9841e070dd4c0d12c839f7bb397c509d8179446187499ff1530667577fea2c16", 15136),
    "5.stl": ("8fe6b8f592febc58d9e7c9d383b31bea899720ed9898e428142c5d0e6684536c", 283358),
    "6.stl": ("0a543b69180ae64baec9175401574610c67b6aabffda277474db54e031058e18", 520296),
    "7.stl": ("c9545e25ee817e804916383858ca617a9789ea330c3776563eceb71c1793c71f", 6483),
    "8.stl": ("ee1a6683a7965ff51631563b81aa8d929bfbd2ada103e072aff5f8e2a59345c0", 615416),
    "9.stl": ("8cefb9fe2cc970f92a3e5b4422a167892b742cf3ac58929347f17ada65d03d90", 520193),
    "A.stl": ("cd45358c02f3215fee769f32b05b777e6ac6289de59de7481217757c7686d4b9", 11878),
    "B.stl": ("2968f24e220764abdf973ce3eaeddfea79b8385b2e8d936952286bb519faa8d4", 309210),
    "C.stl": ("0ade50ee6ee506b0dec98289102634485f639db790439f29f341de089cbbbcd0", 319092),
    "Colosseum_final.stl": ("5eeede281a73220b5c71e7a9186a7def6ebb2459fd7ea598225623474c72d90d", 39272784),
    "D.stl": ("1475a63e949cec68ff61acdcc06ce9e3abf55ffe1de684786d84c6dd0aaba1bb", 254082),
    "E.stl": ("f1f1b13462c8fa984c735d94e85a7954363832e4e5ad7e896e205ede92ae60d7", 11877),
    "F.stl": ("702c13a7106958f83e929369b2023c3f7adf4a5a1ed8483c2cbbd4f37f2f4dec", 9719),
    "G.stl": ("a030293996c4c45cc80cdbadd393cebddae7531866dc9d147650dddd6f2ac5b3", 310965),
    "H.stl": ("88caf4e727d8f782d7700f6cf531a1f34bc1a7b4766e54cb950a33426a13dddc", 11864),
    "I.stl": ("c1431b6131fd89fc77924c4c8d90de542339ccb82495ac825d8c977f60c64308", 3240),
    "J.stl": ("4c55dd73437458e41903417881c8a0e0c29113a36647857b460c2fdc93ad96d8", 103985),
    "JWST.stl": ("bec484c014fa58318295cf2b3ce009ccd5b0ec4425d21b84eb227a6026dc4b12", 28259584),
    "K.stl": ("6aa9d15d28de556dadd0f76eced7c1ffdb77ea610ba9689f3cf938e0bf5f3ccc", 10780),
    "L.stl": ("350548f505f5aff1e92772670d70b2079c1d6a1b88902b1b11c83df3d859688b", 5399),
    "Letter_A.stl": ("cd45358c02f3215fee769f32b05b777e6ac6289de59de7481217757c7686d4b9", 11878),
    "Letter_B.stl": ("2968f24e220764abdf973ce3eaeddfea79b8385b2e8d936952286bb519faa8d4", 309210),
    "Letter_C.stl": ("0ade50ee6ee506b0dec98289102634485f639db790439f29f341de089cbbbcd0", 319092),
    "Letter_D.stl": ("1475a63e949cec68ff61acdcc06ce9e3abf55ffe1de684786d84c6dd0aaba1bb", 254082),
    "Letter_E.stl": ("f1f1b13462c8fa984c735d94e85a7954363832e4e5ad7e896e205ede92ae60d7", 11877),
    "Letter_F.stl": ("702c13a7106958f83e929369b2023c3f7adf4a5a1ed8483c2cbbd4f37f2f4dec", 9719),
    "Letter_G.stl": ("a030293996c4c45cc80cdbadd393cebddae7531866dc9d147650dddd6f2ac5b3", 310965),
    "Letter_H.stl": ("88caf4e727d8f782d7700f6cf531a1f34bc1a7b4766e54cb950a33426a13dddc", 11864),
    "Letter_I.stl": ("c1431b6131fd89fc77924c4c8d90de542339ccb82495ac825d8c977f60c64308", 3240),
    "Letter_J.stl": ("4c55dd73437458e41903417881c8a0e0c29113a36647857b460c2fdc93ad96d8", 103985),
    "Letter_K.stl": ("6aa9d15d28de556dadd0f76eced7c1ffdb77ea610ba9689f3cf938e0bf5f3ccc", 10780),
    "Letter_L.stl": ("350548f505f5aff1e92772670d70b2079c1d6a1b88902b1b11c83df3d859688b", 5399),
    "Letter_M.stl": ("620a68a7287814ebe91f35e71425c52aa6dca933ec2758d7332b99fe14aa2de2", 12950),
    "Letter_N.stl": ("6fd5bf496531ffac07beeb4c3214ad56e1005a1b2dafa89b7db690a87107a0b6", 9706),
    "Letter_O.stl": ("84603602a106803efe411ca54e585827e371d6d8c81d67a41cdd5a5e9db78146", 436974),
    "Letter_P.stl": ("85f9d48d31889de84becd2de247d50dd0f2da05e2db58befc30c230e5ae661b4", 170815),
    "Letter_Q.stl": ("1ef202b87881754cb020e7ef41059b9a04e7e949e8ef602c7ccc281658ea7e76", 416979),
    "Letter_R.stl": ("17da27ead208d6aba63952c1a8a9296557ff4181503c33b1134c6e2683a5ac8b", 229256),
    "Letter_S.stl": ("138b2854b47b634dae7b88f98a25aeba8b760c9e6c57243d9150450675642294", 428934),
    "Letter_T.stl": ("7d7dde4e3a0615902f246624ad8c0a4353e800115000489a88480268f67d1e12", 7566),
    "Letter_U.stl": ("0ac0da8546b04b38180fe9573cfa3be1122ef82abcadd50c846fdd16e44c66dd", 206551),
    "Letter_V.stl": ("9e411998eeb0045ec8f692fe9664639f7ad17ee672bb0c20a67c442bc98c606e", 6463),
    "Letter_W.stl": ("2f1736cc143a8e6fb0b41bffd0e30b6df43448957e34bf22bd6be3950cc6bc64", 12925),
    "Letter_X.stl": ("f1ec74bda38916d2b7204d785b8341e023ca2a4dfaa49c0e7e3607603484b173", 11870),
    "Letter_Y.stl": ("e794a68f0016ea96b72e33011bf169715d4072d8a70574ffb4fd9c1b320df952", 8634),
    "Letter_Z.stl": ("84409012f360ac4d44c2506b4297eca42947c630bbd954ab40562485d1219c06", 9720),
    "M.stl": ("620a68a7287814ebe91f35e71425c52aa6dca933ec2758d7332b99fe14aa2de2", 12950),
    "N.stl": ("6fd5bf496531ffac07beeb4c3214ad56e1005a1b2dafa89b7db690a87107a0b6", 9706),
    "O.stl": ("84603602a106803efe411ca54e585827e371d6d8c81d67a41cdd5a5e9db78146", 436974),
    "P.stl": ("85f9d48d31889de84becd2de247d50dd0f2da05e2db58befc30c230e5ae661b4", 170815),
    "Q.stl": ("1ef202b87881754cb020e7ef41059b9a04e7e949e8ef602c7ccc281658ea7e76", 416979),
    "R.stl": ("17da27ead208d6aba63952c1a8a9296557ff4181503c33b1134c6e2683a5ac8b", 229256),
    "S.stl": ("138b2854b47b634dae7b88f98a25aeba8b760c9e6c57243d9150450675642294", 428934),
    "T-Rex.stl": ("4260b78ddf5dac97d4686cce9f1ce0026c70ccc782fd0cd7c0154f33040266bd", 42461084),
    "T.stl": ("7d7dde4e3a0615902f246624ad8c0a4353e800115000489a88480268f67d1e12", 7566),
    "U.stl": ("0ac0da8546b04b38180fe9573cfa3be1122ef82abcadd50c846fdd16e44c66dd", 206551),
    "V.stl": ("9e411998eeb0045ec8f692fe9664639f7ad17ee672bb0c20a67c442bc98c606e", 6463),
    "W.stl": ("2f1736cc143a8e6fb0b41bffd0e30b6df43448957e34bf22bd6be3950cc6bc64", 12925),
    "X.stl": ("f1ec74bda38916d2b7204d785b8341e023ca2a4dfaa49c0e7e3607603484b173", 11870),
    "Y.stl": ("e794a68f0016ea96b72e33011bf169715d4072d8a70574ffb4fd9c1b320df952", 8634),
    "Z.stl": ("84409012f360ac4d44c2506b4297eca42947c630bbd954ab40562485d1219c06", 9720),
    "alicorn-rmd-repaired.stl": ("7b755b5910773e4a9f6ef805d34a25792b8dfff19eefb5a8c36df9f052357973", 22551884),
    "alicorn-side1.stl": ("1d658d8755e78c3d2e08c67f8433cb602cc4fbff94c27858817b1c9d2c04b03f", 11594684),
    "alicorn-side2.stl": ("0c4c2b74bbcf469aaffa7426219925c275b723d31c558e9258098355fc2ab7ce", 11227934),
    "ampersand.stl": ("d62ad3ef74a9f85f92ac1779de3f475fec4aa9e2b99adf98f6487176163a9a22", 389361),
    "at.stl": ("aff4ec337ca61cedf51d083f4178e735f64ff034358bd111ff6649007da6fcba", 724748),
    "bracket_open_close.stl": ("d17ad4d6d7d21cb1311f4db6c98118339585e6cd98f64c00a2779ac83ab6528d", 240103),
    "carnival_wheel_assy.STL": ("f544bad379fcdea8b6e82d7d690ad71afee04bf105d947156fc2b4fe82d35348", 1218684),
    "dollar.stl": ("baf5a22766d6af59e0c988459b1b621c06c1795e14724f865e3f688f8a1b1485", 378502),
    "euro_sign.stl": ("4d6e695d544fef6b34acbfd167196c0cca3c008897cc282c53a6caeb866f41b5", 305013),
    "exclamation.stl": ("ad02c3fc46ee5010516a7e86ba32b592d43046852443959105183d24fcb1e29c", 8649),
    "gumball_machine.STL": ("b6da2c4cff3b5c5fa5e20608e30813db5d169b9cff4ffdb654dd1f80447e34c5", 272684),
    "hash.stl": ("9873c4f20cb93a8bd5ffb83affcf0d6bca501096148bed3ad43ea34a5e648940", 34601),
    "hyphen.stl": ("640a7536253c81a361372416d26bd0a695350a0837fe52bd7bdc6334ac14f957", 3261),
    "plus.stl": ("c14c9096beb912887aa93cff0b65e28b2339fedce0d69e95ac924ee8c0860a16", 11891),
    "pound_sign.stl": ("aa210714c8cacc3b6e6bf38f0d2937947047b01c0e03d2f60e61a861e23a4cf7", 148167),
    "question_mark.stl": ("d30ee3be68c533d7ba585c9ca17667a436dc83cdac029de71149ade49d718eaa", 248209),
    "section_sign.stl": ("d8f553057509973f073b1732da6fdea392bfe7b681a51d5c90bd35ab1821fd84", 619721),
    "taj-mahal-by-miniworld3d.stl": ("973c4993c5a23ca3038dc953012ddebd3eb050a0170fc61c24f7bfd921b63825", 6857084),
    "yen_sign.stl": ("f73982812e2d3c454b58525503b4ce78ae6d5865290d1c0b3c5f121d19922618", 42106),
}


class ModelError(Exception):
    """A model could not be fetched, or arrived damaged."""


def _digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _looks_right(path, expected_sha, expected_size):
    return (path.is_file()
            and path.stat().st_size == expected_size
            and _digest(path) == expected_sha)


def ensure(name, quiet=False):
    """Return the path to a model, downloading it if it is not already here."""
    if name not in MODELS:
        raise ModelError(
            "%s is not one of the published models. Known models: %s"
            % (name, ", ".join(sorted(MODELS))))

    expected_sha, expected_size = MODELS[name]
    path = DATA_DIR / name

    if _looks_right(path, expected_sha, expected_size):
        return path

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not quiet:
        print("Downloading %s (%.1f MB), one time only..."
              % (name, expected_size / 1048576), flush=True)

    # Download beside the target and move it into place, so an interrupted
    # download never leaves half a model behind that looks real to the next run.
    partial = path.with_suffix(path.suffix + ".part")
    try:
        with urllib.request.urlopen(RELEASE_URL + name) as response:
            with open(partial, "wb") as out:
                shutil.copyfileobj(response, out)
    except urllib.error.URLError as exc:
        if partial.exists():
            partial.unlink()
        raise ModelError(
            "Could not download %s: %s. The models are at %s if you would "
            "rather fetch them by hand." % (name, exc, RELEASE_URL)) from exc

    if not _looks_right(partial, expected_sha, expected_size):
        if partial.exists():
            partial.unlink()
        raise ModelError(
            "%s downloaded but did not match its checksum, so it arrived "
            "damaged or the release was changed. Try again." % name)

    partial.replace(path)
    return path


# Character to model filename, for message.py.
#
# Letters and digits are named after themselves. Symbols are not: GitHub
# rejects "#.stl" outright and silently renames "&.stl" to "default.stl", so
# they get descriptive names -- which is what the repository already did for
# euro_sign.stl and friends.
SYMBOL_FILES = {
    "!": "exclamation.stl",
    "#": "hash.stl",
    "$": "dollar.stl",
    "&": "ampersand.stl",
    "+": "plus.stl",
    "-": "hyphen.stl",
    "@": "at.stl",
    "?": "question_mark.stl",
    "(": "bracket_open_close.stl",
    ")": "bracket_open_close.stl",
    "£": "pound_sign.stl",
    "€": "euro_sign.stl",
    "¥": "yen_sign.stl",
    "§": "section_sign.stl",
}


def character(c):
    """The model for a single character, or None if there is not one.

    Returns None rather than raising for an unknown character, so a caller can
    skip a space or an emoji without special-casing every possibility.
    """
    if c.isalnum():
        name = c.upper() + ".stl"
    else:
        name = SYMBOL_FILES.get(c)
    if name is None or name not in MODELS:
        return None
    return ensure(name)


def ensure_all(quiet=False):
    """Fetch every model. Mostly useful before going offline."""
    return [ensure(name, quiet=quiet) for name in sorted(MODELS)]


def letters(word):
    """Paths to the models spelling a word, skipping anything with no model."""
    return [p for p in (character(c) for c in word) if p is not None]


if __name__ == "__main__":
    wanted = sys.argv[1:] or sorted(MODELS)
    try:
        for model in wanted:
            print(ensure(model))
    except ModelError as problem:
        raise SystemExit(str(problem))
