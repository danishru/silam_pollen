import React from 'react';
import {useThemeConfig} from '@docusaurus/theme-common';
import NavbarItem from '@theme/NavbarItem';

function useNavbarItems() {
  return useThemeConfig().navbar.items;
}

export default function NavbarMobilePrimaryMenu() {
  const items = useNavbarItems().filter((item) => item.type !== 'localeDropdown');

  return (
    <ul className="menu__list">
      {items.map((item, i) => (
        <NavbarItem mobile {...item} key={i} />
      ))}
    </ul>
  );
}
