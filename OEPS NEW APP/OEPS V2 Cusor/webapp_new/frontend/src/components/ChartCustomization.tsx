import React from 'react';
import styled from 'styled-components';

const Container = styled.div`
  padding: 1rem;
  background-color: ${props => props.theme.background};
  border: 1px solid ${props => props.theme.border};
  border-radius: 4px;
  margin-bottom: 1rem;
`;

const Title = styled.h3`
  margin: 0 0 1rem 0;
  color: ${props => props.theme.text};
`;

const ControlGroup = styled.div`
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 1rem;
`;

const Label = styled.label`
  color: ${props => props.theme.text};
  font-size: 0.875rem;
`;

const Select = styled.select`
  padding: 0.5rem;
  border: 1px solid ${props => props.theme.border};
  border-radius: 4px;
  background-color: ${props => props.theme.background};
  color: ${props => props.theme.text};
  font-size: 0.875rem;
`;

const Input = styled.input`
  padding: 0.5rem;
  border: 1px solid ${props => props.theme.border};
  border-radius: 4px;
  background-color: ${props => props.theme.background};
  color: ${props => props.theme.text};
  font-size: 0.875rem;
`;

const ColorInput = styled.input`
  width: 100%;
  height: 32px;
  padding: 0;
  border: 1px solid ${props => props.theme.border};
  border-radius: 4px;
  background-color: ${props => props.theme.background};
`;

interface ChartStyle {
  lineColor: string;
  backgroundColor: string;
  lineWidth: number;
  lineStyle: 'solid' | 'dashed' | 'dotted';
  pointStyle: 'circle' | 'square' | 'triangle' | 'cross';
  pointSize: number;
  tension: number;
}

interface ChartCustomizationProps {
  style: ChartStyle;
  onChange: (style: ChartStyle) => void;
}

const ChartCustomization: React.FC<ChartCustomizationProps> = ({ style, onChange }) => {
  const handleChange = (key: keyof ChartStyle, value: string | number) => {
    onChange({ ...style, [key]: value });
  };

  return (
    <Container>
      <Title>Chart Customization</Title>
      <ControlGroup>
        <Label>Line Color</Label>
        <ColorInput
          type="color"
          value={style.lineColor}
          onChange={(e) => handleChange('lineColor', e.target.value)}
        />
      </ControlGroup>
      <ControlGroup>
        <Label>Background Color</Label>
        <ColorInput
          type="color"
          value={style.backgroundColor}
          onChange={(e) => handleChange('backgroundColor', e.target.value)}
        />
      </ControlGroup>
      <ControlGroup>
        <Label>Line Width</Label>
        <Input
          type="range"
          min="1"
          max="5"
          step="0.5"
          value={style.lineWidth}
          onChange={(e) => handleChange('lineWidth', parseFloat(e.target.value))}
        />
      </ControlGroup>
      <ControlGroup>
        <Label>Line Style</Label>
        <Select
          value={style.lineStyle}
          onChange={(e) => handleChange('lineStyle', e.target.value as ChartStyle['lineStyle'])}
        >
          <option value="solid">Solid</option>
          <option value="dashed">Dashed</option>
          <option value="dotted">Dotted</option>
        </Select>
      </ControlGroup>
      <ControlGroup>
        <Label>Point Style</Label>
        <Select
          value={style.pointStyle}
          onChange={(e) => handleChange('pointStyle', e.target.value as ChartStyle['pointStyle'])}
        >
          <option value="circle">Circle</option>
          <option value="square">Square</option>
          <option value="triangle">Triangle</option>
          <option value="cross">Cross</option>
        </Select>
      </ControlGroup>
      <ControlGroup>
        <Label>Point Size</Label>
        <Input
          type="range"
          min="0"
          max="8"
          step="1"
          value={style.pointSize}
          onChange={(e) => handleChange('pointSize', parseInt(e.target.value))}
        />
      </ControlGroup>
      <ControlGroup>
        <Label>Line Tension</Label>
        <Input
          type="range"
          min="0"
          max="1"
          step="0.1"
          value={style.tension}
          onChange={(e) => handleChange('tension', parseFloat(e.target.value))}
        />
      </ControlGroup>
    </Container>
  );
};

export default ChartCustomization; 