# Third-party notices

## mpy-img-decoder JPEG decoder

`lib/JPEGdecoder.py` is the existing pure-MicroPython decoder retained by this
project. Its header identifies Mats Alritzson as the original copyright holder
and Remixer Dec as the MicroPython porter. It is licensed under the GNU General
Public License, version 3 or (at the recipient's option) any later version.

Source/project lineage: `mpy-img-decoder`, ported from `enmasse/jpeg_read`.
The decoder file's copyright and license header must remain intact. When
distributing firmware containing it, provide the corresponding source and a
copy of GPLv3 as required by that license.

The PlantGuard integration modules call the decoder through its documented
pixel callback interface and do not remove or weaken its license terms.

