import { useState, useEffect } from 'react'
import { Container, Heading, VStack, SimpleGrid, useToast } from '@chakra-ui/react'
import { packageAPI, Package } from '../services/api'
import SearchBar from '../components/SearchBar'
import PackageCard from '../components/PackageCard'

export default function Directory() {
  const [packages, setPackages] = useState<Package[]>([])
  const [searchQuery, setSearchQuery] = useState('')
  const toast = useToast()

  useEffect(() => {
    loadPackages()
  }, [])

  const loadPackages = async () => {
    try {
      const response = await packageAPI.getAll()
      setPackages(response.data)
    } catch (error) {
      toast({
        title: 'Error loading packages',
        status: 'error',
        duration: 3000,
      })
    }
  }

  const handleSearch = async () => {
    if (!searchQuery) {
      loadPackages()
      return
    }
    try {
      const response = await packageAPI.search(searchQuery)
      setPackages(response.data)
    } catch (error) {
      toast({
        title: 'Search failed',
        status: 'error',
        duration: 3000,
      })
    }
  }

  const handleDownload = async (pkg: Package) => {
    try {
      const response = await packageAPI.download(pkg.name, pkg.version)
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.download = `${pkg.name}-${pkg.version}.zip`
      link.click()
    } catch (error) {
      toast({
        title: 'Download failed',
        status: 'error',
        duration: 3000,
      })
    }
  }

  return (
    <Container maxW="container.xl" py={10}>
      <VStack spacing={6} align="stretch">
        <Heading as="h1" size="xl">
          Package Directory
        </Heading>
        <SearchBar 
          value={searchQuery} 
          onChange={(value) => {
            setSearchQuery(value)
            if (value) handleSearch()
            else loadPackages()
          }} 
        />
        <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
          {packages.map((pkg) => (
            <PackageCard key={pkg.id} package={pkg} onDownload={() => handleDownload(pkg)} />
          ))}
        </SimpleGrid>
      </VStack>
    </Container>
  )
}

