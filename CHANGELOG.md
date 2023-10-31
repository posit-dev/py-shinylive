# Change Log for Shinylive

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2023-10-31

* Adjusted cli api to have all quarto extension commands under `extension`. (#16)

### Library updates

* Updated to Shinylive web assets 0.2.2.

## [0.0.18] - 2023-09-13

### Library updates

* Updated to Shinylive web assets 0.2.0.

## [0.0.17] - 2023-08-23

### Library updates

* Updated to Shinylive web assets 0.1.6.

## [0.0.16] - 2023-08-08

### Library updates

* Updated to Shinylive web assets 0.1.5.


## [0.0.15] - 2023-06-27

### Library updates

* Updated to Shinylive web assets 0.1.4.

### Bug fixes

* Fixed a bug where, if a module name did not match the name of the package (e.g., "cv2" and "opencv-python"), then `shinylive export` would fail to copy the package. (#7)


## [0.0.14] - 2023-06-27

### Library updates

* Updated to Shinylive web assets 0.1.3.


## [0.0.13] - 2023-04-19

### Library updates

* Updated to Shinylive web assets 0.1.2.


## [0.0.12] - 2023-04-19

### Library updates

* Updated to Shinylive web assets 0.1.1.


## [0.0.11] - 2023-04-18

### Library updates

* Updated to Shinylive web assets 0.1.0.


## [0.0.10] - 2023-04-13

### Library updates

* Updated to Shinylive web assets 0.0.13.


## [0.0.9] - 2023-03-02

### Library updates

* Updated to Shinylive web assets 0.0.12.


## [0.0.8] - 2022-10-26

### New features

* Updated to Shinylive web assets 0.0.11.

### Bug fixes

* Added fix to avoid tarfile path traversal (CVE-2007-4559). (#3)


## [0.0.7] - 2022-09-26

### Library updates

* Updated to Shinylive web assets 0.0.10.


## [0.0.6] - 2022-09-21

### New features

* Updated to Shinylive web assets 0.0.9.

### Bug fixes

* Fixed bug in removal of symlinked asset directories.


## [0.0.5] - 2022-09-20

### New features

* Added `shinylive assets version` command, which prints out the version of the Shinylive web assets.

### Bug fixes

* Fixed #1: `verbose_print()` raised an error due to an extra argument.


## [0.0.4] - 2022-09-19

### New features

* Added `shinylive assets link-from-local` command.

* Print messages to stderr instead of stdout.


## [0.0.3] - 2022-09-16

### New features

* Updated command-line tool to work better with Quarto extension.


## [0.0.2] - 2022-09-02

### New features

* Changed `shinylive deploy` to `shinylive export`.

* Update to use Shinylive web assets version 0.0.7.
