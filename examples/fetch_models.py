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
    "JWST.stl": ("bec484c014fa58318295cf2b3ce009ccd5b0ec4425d21b84eb227a6026dc4b12", 28259584),
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
    "T-Rex.stl": ("4260b78ddf5dac97d4686cce9f1ce0026c70ccc782fd0cd7c0154f33040266bd", 42461084),
    "carnival_wheel_assy.STL": ("f544bad379fcdea8b6e82d7d690ad71afee04bf105d947156fc2b4fe82d35348", 1218684),
    "gumball_machine.STL": ("b6da2c4cff3b5c5fa5e20608e30813db5d169b9cff4ffdb654dd1f80447e34c5", 272684),
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


def ensure_all(quiet=False):
    """Fetch every model. Mostly useful before going offline."""
    return [ensure(name, quiet=quiet) for name in sorted(MODELS)]


def letters(word):
    """Paths to the letter models spelling a word, e.g. letters("HI")."""
    return [ensure("Letter_%s.stl" % c) for c in word.upper() if c.isalpha()]


if __name__ == "__main__":
    wanted = sys.argv[1:] or sorted(MODELS)
    try:
        for model in wanted:
            print(ensure(model))
    except ModelError as problem:
        raise SystemExit(str(problem))
