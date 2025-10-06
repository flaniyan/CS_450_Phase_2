import { useState } from 'react'
import { Container, Heading, VStack, Button, Input, Checkbox, useToast, FormControl, FormLabel } from '@chakra-ui/react'
import { packageAPI } from '../services/api'

export default function Upload() {
  const [file, setFile] = useState<File | null>(null)
  const [debloat, setDebloat] = useState(false)
  const [uploading, setUploading] = useState(false)
  const toast = useToast()

  const handleUpload = async () => {
    if (!file) {
      toast({
        title: 'Please select a file',
        status: 'warning',
        duration: 3000,
      })
      return
    }

    setUploading(true)
    try {
      await packageAPI.upload(file, debloat)
      toast({
        title: 'Package uploaded successfully',
        status: 'success',
        duration: 3000,
      })
      setFile(null)
      setDebloat(false)
    } catch (error) {
      toast({
        title: 'Upload failed',
        status: 'error',
        duration: 3000,
      })
    } finally {
      setUploading(false)
    }
  }

  return (
    <Container maxW="container.md" py={10}>
      <VStack spacing={6} align="stretch">
        <Heading as="h1" size="xl">
          Upload Package
        </Heading>
        <FormControl>
          <FormLabel htmlFor="file-upload">Select .zip file</FormLabel>
          <Input
            id="file-upload"
            type="file"
            accept=".zip"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            aria-label="Upload package file"
            p={1}
          />
        </FormControl>
        <Checkbox 
          isChecked={debloat} 
          onChange={(e) => setDebloat(e.target.checked)}
          aria-label="Enable debloat"
        >
          Enable debloat
        </Checkbox>
        <Button 
          colorScheme="green" 
          onClick={handleUpload} 
          isLoading={uploading}
          isDisabled={!file}
          aria-label="Upload package"
        >
          Upload
        </Button>
      </VStack>
    </Container>
  )
}

