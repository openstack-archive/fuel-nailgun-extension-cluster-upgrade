Name:           fuel-nailgun-extension-cluster-upgrade
Version:        10.0~b1
Release:        1%{?dist}
Summary:        Cluster upgrade extension for Fuel
License:        Apache-2.0
Url:            https://git.openstack.org/cgit/openstack/fuel-nailgun-extension-cluster-upgrade/
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  python-devel
BuildRequires:  python-pbr
BuildRequires:  python-setuptools

Requires:       fuel-nailgun
Requires:       python-pbr

%description
Cluster upgrade extension for Fuel

%prep
%setup -q -c -n %{name}-%{version}

%build
export OSLO_PACKAGE_VERSION=%{version}
%py2_build

%install
export OSLO_PACKAGE_VERSION=%{version}
%py2_install

%files
%license LICENSE
%{python2_sitelib}/cluster_upgrade
%{python2_sitelib}/*.egg-info

%changelog
* Thu Aug 04 2016 Alexander Tsamutali <atsamutali@mirantis.com> - 10.0~b1-1
- Initial package.
