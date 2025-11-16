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

### Overriding AppStream metadata while retaining RPM-generated data

You can use both the RPM-generated AppStream metadata and a minimal override file to customize specific fields.

To do this, create a minimal generic metainfo XML file with only the fields you want to override, for example:

```xml
<component>
    <name>Custom Package Name</name>
    <summary>Custom summary for my package.</summary>
    <launchable type="desktop-id">my.custom.package.id.desktop</launchable>
</component>
```

Then, in your specfile, use the `-o` option to specify this override file, just like when using a base file:

```rpmspec
%global appid my.package.id
%global appstream_component desktop-application
Source1: my-package-override.metainfo.xml
...

%terra_appstream -o %{SOURCE1}
```

This will use the minimal component as a base and merge the RPM-generated metadata into it, with the RPM-generated data only appending fields that are missing from the override file.

```xml
<component type="desktop-application">
    <id>my.package.id</id>
    <name>Custom Package Name</name>
    <summary>Custom summary for my package.</summary>
    <launchable type="desktop-id">my.custom.package.id.desktop</launchable>
    ...
</component>
```

## How it works
terra-appstream-helper does a 1-3 way merge from:
1. The base file provided with `-o` (if any)
2. The RPM-generated metadata from the macros in the specfile
3. The upstream metainfo file (if any) installed to the buildroot earlier in the %install section.

The merge order is that the topmost source will take precedence over the lower sources for any fields that are present in multiple sources.

### Supported macros

The following RPM macros are supported to customize the AppStream metadata:

- `appid`: The AppStream ID for the package (e.g., `com.example.my-package`). Required for all packages that use this macro.
- `developer`: The name of the upstream developer or organization.
- `org`: The organization domain of the upstream developer (e.g., `org.example`).
- `license`: The license of the package (e.g., `MIT`, `GPL-3.0-or-later`). Should already be filled in by the `License:` preamble
- `url`: The URL of the package's homepage. Should already be filled in by the `URL:` preamble
- `appstream_component`: The component type of the package (e.g., `desktop-application`, `console-application`, `runtime`, etc.).
- `description`: A short description of the package.