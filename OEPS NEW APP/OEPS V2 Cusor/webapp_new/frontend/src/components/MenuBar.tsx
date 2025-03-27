import React from 'react';
import styled from 'styled-components';
import { Theme } from '../theme';

const MenuContainer = styled.div<{ theme: Theme }>`
  background-color: ${props => props.theme.background};
  border-bottom: 1px solid ${props => props.theme.border};
  padding: 0.5rem 1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
`;

const MenuGroup = styled.div<{ theme: Theme }>`
  display: flex;
  gap: 1rem;
  align-items: center;
`;

const MenuItem = styled.button<{ active?: boolean; theme: Theme }>`
  background: none;
  border: none;
  color: ${props => props.active ? props.theme.primary : props.theme.text};
  padding: 0.5rem 1rem;
  cursor: pointer;
  font-size: 1rem;
  border-radius: 4px;
  transition: all 0.2s;

  &:hover {
    background-color: ${props => props.theme.hover};
  }

  &:active {
    background-color: ${props => props.theme.active};
  }
`;

const DropdownPanel = styled.div<{ isOpen: boolean }>`
  position: absolute;
  top: 100%;
  right: 0;
  width: 300px;
  background-color: ${props => props.theme.background};
  border: 1px solid ${props => props.theme.border};
  border-radius: 4px;
  padding: 1rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  z-index: 100;
  display: ${props => props.isOpen ? 'block' : 'none'};
  margin-top: 0.5rem;
`;

const InputGroup = styled.div`
  margin-bottom: 1rem;

  &:last-child {
    margin-bottom: 0;
  }
`;

const Label = styled.label`
  display: block;
  margin-bottom: 0.5rem;
  color: ${props => props.theme.text};
  font-size: 0.875rem;
`;

const Input = styled.input`
  width: 100%;
  padding: 0.5rem;
  border: 1px solid ${props => props.theme.border};
  border-radius: 4px;
  background-color: ${props => props.theme.background};
  color: ${props => props.theme.text};
`;

const Select = styled.select`
  width: 100%;
  padding: 0.5rem;
  border: 1px solid ${props => props.theme.border};
  border-radius: 4px;
  background-color: ${props => props.theme.background};
  color: ${props => props.theme.text};
`;

const Button = styled.button`
  padding: 0.5rem 1rem;
  background-color: ${props => props.theme.primary};
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  margin-top: 1rem;

  &:hover {
    opacity: 0.9;
  }
`;

const ColorInput = styled.input`
  width: 100%;
  padding: 0.5rem;
  border: 1px solid ${props => props.theme.border};
  border-radius: 4px;
  background-color: ${props => props.theme.background};
  color: ${props => props.theme.text};
`;

const RangeInput = styled.input`
  width: 100%;
  margin: 0.5rem 0;
`;

interface MeasurementSettings {
  startPotential: number;
  endPotential: number;
  scanRate: number;
  currentRange: string;
  duration: number;
  interval: number;
}

interface ChartStyle {
  lineColor: string;
  backgroundColor: string;
  lineWidth: number;
  lineStyle: 'solid' | 'dashed' | 'dotted';
  pointStyle: 'circle' | 'square' | 'triangle' | 'cross';
  pointSize: number;
  tension: number;
}

interface MenuBarProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
  onThemeToggle: () => void;
}

const MenuBar: React.FC<MenuBarProps> = ({ activeTab, onTabChange, onThemeToggle }) => {
  return (
    <MenuContainer>
      <MenuGroup>
        <MenuItem
          active={activeTab === 'dashboard'}
          onClick={() => onTabChange('dashboard')}
        >
          Dashboard
        </MenuItem>
        <MenuItem
          active={activeTab === 'data'}
          onClick={() => onTabChange('data')}
        >
          Data
        </MenuItem>
        <MenuItem
          active={activeTab === 'settings'}
          onClick={() => onTabChange('settings')}
        >
          Settings
        </MenuItem>
      </MenuGroup>
      <MenuGroup>
        <MenuItem onClick={onThemeToggle}>
          Toggle Theme
        </MenuItem>
      </MenuGroup>
    </MenuContainer>
  );
};

export default MenuBar; 