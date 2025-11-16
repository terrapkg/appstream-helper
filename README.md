# Terra AppStream Helper

This repository contains a Python script and RPM macros
to help package AppStream metadata for packages on Terra.

## Usage

New packages in Terra should include AppStream metadata for
discoverability in package managers that support it.

To use the AppStream helper, modify your specfile like so:

```rpmspec
%global appid my.package.id
%global developer "Upstream Developer"
%global org "org.upstream"

Name: my-package
Version: 1.0
Release: 1%{?dist}
Summary: My Package Summary
License: MIT
URL: https://example.com/my-package

%description
...

%prep
...
%build
...
%install
...
# Append this line to the end of your %install section, after
# all files have been installed to %{buildroot}
# Upstream package-installed metainfo will be merged and amended to
# if found.
%terra_appstream
```


If you want to customize the AppStream metadata further, you can create a base AppStream metainfo file to merge all other changes into, like so:

```rpmspec
...
Source1: com.example.my-package.metainfo.xml

...
%install

...
%terra_appstream -o %{SOURCE1}
```

This will use the provided metainfo file as a base and merge
all other changes into it if found.

### Supported macros

The following RPM macros are supported to customize the AppStream metadata:

- `appid`: The AppStream ID for the package (e.g., `com.example.my-package`).
- `developer`: The name of the upstream developer or organization.
- `org`: The organization domain of the upstream developer (e.g., `org.example`).
- `license`: The license of the package (e.g., `MIT`, `GPL-3.0-or-later`). Should already be filled in by the `License:` preamble
- `url`: The URL of the package's homepage. Should already be filled in by the `URL:` preamble
- `appstream_component`: The component type of the package (e.g., `desktop-application`, `console-application`, `runtime`, etc.).
- `description`: A short description of the package.