# Change Log for Shinylive

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.1] - 2024-11-12

* Updated to Shinylive web assets 0.9.1.

## [0.7.0] - 2024-10-29

* Updated to Shinylive web assets 0.9.0.

* Download status is now displayed while downloading Shinylive assets.

## [0.6.0] - 2024-09-03

* Updated to Shinylive web assets 0.6.0.

* Fixed a problem with dependency detection when the package name differed from the key in package-lock.json (#36).

## [0.5.0] - 2024-07-18

* Updated to Shinylive web assets 0.5.0.

* `shinylive.export()` gains `template_params` and `template_dir` arguments that are reflected in the CLI as `--template-params` and `--template-dir` arguments to `shinylive export`.

  These options control the template HTML files used in the export, allowing users to partially or completely customize the exported HTML. The export template is provided by the shinylive assets and may change from release-to-release. Use `shinylive assets info` to locate installed shinylive assets; the template files for a given release are in the `export_template` directory of the release. (#32)
    * `template_params` takes a list of parameters to be interpolated into the template. In the CLI `--template-params` takes a string of JSON or a path to a JSON file. The default template includes `title` (the title for the page with the exported app), `include_in_head` (HTML added to the `<head>` of the page), and `include_before_body` (HTML added just after `<body>`) and `include_after_body` (HTML added just after `</body>`).
    * `template_dir` is the directory containing the template files. The default is the `export_template` directory of the shinylive assets being used for the export. Use `shinylive assets info` to locate installed shinylive assets where you can find the default template files.


## [0.4.1] - 2024-05-28

* Updated to Shinylive web assets 0.4.1.

## [0.4.0] - 2024-05-23

* Updated to Shinylive web assets 0.4.0.

* Closed #28: On Windows, extended characters were not handled correctly. Files are now always loaded with UTF-8 encoding. (#29)

## [0.3.0] - 2024-04-16

* Updated to Shinylive web assets 0.3.0.

## [0.2.4] - 2024-03-08

* Updated to Shinylive web assets 0.2.8.

## [0.2.3] - 2024-03-04

* Updated to Shinylive web assets 0.2.7.

## [0.2.2] - 2024-02-05

* Updated to Shinylive web assets 0.2.6.

## [0.2.1] - 2024-01-25

* Added support for packages which are listed in `requirements.txt` and are part of the Pyodide distribution, but are not `import`ed in the code, and are soft dependencies of `import`ed packages (they are optionally loaded, as opposed to hard dependencies which are always loaded). (#25)

## [0.2.0] - 2024-01-25

* Added `shinylive url encode` and `shinylive url decode` commands to encode local apps into a [shinylive.io](https://shinylive.io) URL or decode a [shinylive.io](https://shinylive.io) URL into local files. These commands are accompanied by `url_encode()` and `url_decode()` functions for programmatic use. They are supported by the new `ShinyliveIoApp` class which provides methods to get the app URL, save the app locally, or create a [Shinylive quarto chunk](https://quarto-ext.github.io/shinylive/) from the app's files. (#20, #23)

* Updated to Shinylive web assets 0.2.5.

## [0.1.3] - 2023-12-19

* Fixed `shinylive assets install-from-local`.

* Updated to Shinylive web assets 0.2.4.

## [0.1.2] - 2023-11-30

### Library updates

* Updated to Shinylive web assets 0.2.3.

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
