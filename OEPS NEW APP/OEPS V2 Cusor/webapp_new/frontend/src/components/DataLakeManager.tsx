import React, { useState, useCallback } from 'react';
import styled from 'styled-components';
import { Theme } from '../theme';
import { useDropzone } from 'react-dropzone';
import DataVisualization from './DataVisualization';

const Container = styled.div<{ theme: Theme }>`
  padding: 1rem;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 1rem;
`;

const Header = styled.div<{ theme: Theme }>`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
`;

const Title = styled.h2<{ theme: Theme }>`
  color: ${props => props.theme.text};
  margin: 0;
`;

const Button = styled.button<{ theme: Theme }>`
  padding: 0.5rem 1rem;
  background-color: ${props => props.theme.primary};
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    opacity: 0.9;
  }
`;

const Content = styled.div<{ theme: Theme }>`
  display: flex;
  gap: 1rem;
  flex: 1;
  overflow: hidden;
`;

const Sidebar = styled.div<{ theme: Theme }>`
  width: 250px;
  background-color: ${props => props.theme.background};
  border: 1px solid ${props => props.theme.border};
  border-radius: 4px;
  padding: 1rem;
  overflow-y: auto;
`;

const MainContent = styled.div<{ theme: Theme }>`
  flex: 1;
  background-color: ${props => props.theme.background};
  border: 1px solid ${props => props.theme.border};
  border-radius: 4px;
  padding: 1rem;
  overflow-y: auto;
`;

const FolderItem = styled.div<{ active?: boolean; theme: Theme }>`
  padding: 0.5rem;
  cursor: pointer;
  border-radius: 4px;
  background-color: ${props => props.active ? props.theme.hover : 'transparent'};
  color: ${props => props.theme.text};
  display: flex;
  align-items: center;
  gap: 0.5rem;

  &:hover {
    background-color: ${props => props.theme.hover};
  }
`;

const DataGrid = styled.div<{ theme: Theme }>`
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1rem;
`;

const DataCard = styled.div<{ theme: Theme }>`
  background-color: ${props => props.theme.background};
  border: 1px solid ${props => props.theme.border};
  border-radius: 4px;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
`;

const CardTitle = styled.h3<{ theme: Theme }>`
  color: ${props => props.theme.text};
  margin: 0;
`;

const CardInfo = styled.div<{ theme: Theme }>`
  color: ${props => props.theme.text};
  font-size: 0.875rem;
`;

const CardActions = styled.div<{ theme: Theme }>`
  display: flex;
  gap: 0.5rem;
  margin-top: auto;
`;

const ActionButton = styled.button<{ theme: Theme }>`
  padding: 0.25rem 0.5rem;
  background-color: ${props => props.theme.background};
  color: ${props => props.theme.text};
  border: 1px solid ${props => props.theme.border};
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.875rem;
  transition: all 0.2s;

  &:hover {
    background-color: ${props => props.theme.hover};
  }
`;

const DropZone = styled.div<{ isDragActive: boolean; theme: Theme }>`
  border: 2px dashed ${props => props.isDragActive ? props.theme.primary : props.theme.border};
  border-radius: 4px;
  padding: 2rem;
  text-align: center;
  background-color: ${props => props.isDragActive ? props.theme.hover : props.theme.background};
  color: ${props => props.theme.text};
  cursor: pointer;
  transition: all 0.2s;
  margin-bottom: 1rem;

  &:hover {
    border-color: ${props => props.theme.primary};
  }
`;

interface DataFile {
  id: string;
  name: string;
  date: string;
  type: string;
  size: string;
  status: 'processed' | 'unprocessed';
  path: string;
}

interface Folder {
  id: string;
  name: string;
  path: string;
  files: DataFile[];
  subfolders: Folder[];
}

const DataLakeManager: React.FC = () => {
  const [currentFolder, setCurrentFolder] = useState<Folder | null>(null);
  const [selectedFile, setSelectedFile] = useState<DataFile | null>(null);
  const [folders, setFolders] = useState<Folder[]>([
    {
      id: '1',
      name: 'Measurements',
      path: '/measurements',
      files: [
        {
          id: '1',
          name: 'measurement_20240327_001.csv',
          date: '2024-03-27 10:00:00',
          type: 'Cyclic Voltammetry',
          size: '2.5 MB',
          status: 'processed',
          path: '/measurements/measurement_20240327_001.csv'
        }
      ],
      subfolders: []
    },
    {
      id: '2',
      name: 'Analysis',
      path: '/analysis',
      files: [],
      subfolders: []
    }
  ]);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    // TODO: Implement file upload logic
    console.log('Dropped files:', acceptedFiles);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({ onDrop });

  const handleFolderClick = (folder: Folder) => {
    setCurrentFolder(folder);
    setSelectedFile(null);
  };

  const handleView = (file: DataFile) => {
    setSelectedFile(file);
  };

  const handleAnalyze = (file: DataFile) => {
    // TODO: Implement data analysis functionality
    console.log('Analyze clicked for file:', file);
  };

  const handleDelete = (file: DataFile) => {
    // TODO: Implement file deletion functionality
    console.log('Delete clicked for file:', file);
  };

  const renderFolderContent = () => {
    if (selectedFile) {
      return (
        <div>
          <Button onClick={() => setSelectedFile(null)}>Back to Files</Button>
          <DataVisualization data={[]} /> {/* TODO: Load actual data */}
        </div>
      );
    }

    return (
      <>
        <DropZone {...getRootProps()} isDragActive={isDragActive}>
          <input {...getInputProps()} />
          {isDragActive ? (
            <p>Drop the files here ...</p>
          ) : (
            <p>Drag 'n' drop some files here, or click to select files</p>
          )}
        </DropZone>
        <DataGrid>
          {currentFolder?.files.map(file => (
            <DataCard key={file.id}>
              <CardTitle>{file.name}</CardTitle>
              <CardInfo>Date: {file.date}</CardInfo>
              <CardInfo>Type: {file.type}</CardInfo>
              <CardInfo>Size: {file.size}</CardInfo>
              <CardInfo>Status: {file.status}</CardInfo>
              <CardActions>
                <ActionButton onClick={() => handleView(file)}>View</ActionButton>
                <ActionButton onClick={() => handleAnalyze(file)}>Analyze</ActionButton>
                <ActionButton onClick={() => handleDelete(file)}>Delete</ActionButton>
              </CardActions>
            </DataCard>
          ))}
        </DataGrid>
      </>
    );
  };

  return (
    <Container>
      <Header>
        <Title>Data Lake Manager</Title>
      </Header>
      <Content>
        <Sidebar>
          {folders.map(folder => (
            <FolderItem
              key={folder.id}
              active={currentFolder?.id === folder.id}
              onClick={() => handleFolderClick(folder)}
            >
              📁 {folder.name}
            </FolderItem>
          ))}
        </Sidebar>
        <MainContent>
          {currentFolder ? (
            <>
              <Header>
                <Title>{currentFolder.name}</Title>
              </Header>
              {renderFolderContent()}
            </>
          ) : (
            <p>Select a folder to view its contents</p>
          )}
        </MainContent>
      </Content>
    </Container>
  );
};

export default DataLakeManager; 