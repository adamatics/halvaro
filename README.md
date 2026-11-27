# Halvaro libraries

Business logic libraries of Halvaro Infra, a fictional company: the demo of a FAIR estate on AdaLab by Adamatics. Every name, number and record of the
company is synthetic.

Six Python distributions, one folder each under `libs/`: halvaro-core, halvaro-delivery, halvaro-esg, halvaro-finance, halvaro-grid, halvaro-hr. Each is released on its own, by a tag `<library>/vX.Y.Z`, and installed from the
index `halvaro/libs` on AdaLab's devpi service:

    pip install --index-url https://adalab.adamatics.com/devpi/halvaro/libs/+simple/ halvaro-core

This repository receives a filtered export of the libraries from the closed repository where they are developed. Every commit here is one release tag
there. A pull request is welcome; an accepted change is carried back to the closed repository and comes back with the next export.

Exported from halvaro-finance/v0.1.1 (commit 587082da0d5c70fbb765a167dcc5ced48c0a2763).

Licence: Apache-2.0, see LICENSE.
