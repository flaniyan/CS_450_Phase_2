import { Box, Heading, Text, Progress, VStack } from '@chakra-ui/react'
import { PackageRating } from '../services/api'

interface MetricChartProps {
  rating: PackageRating
}

export default function MetricChart({ rating }: MetricChartProps) {
  const metrics = [
    { name: 'Net Score', value: rating.NetScore },
    { name: 'Ramp Up', value: rating.RampUp },
    { name: 'Correctness', value: rating.Correctness },
    { name: 'Bus Factor', value: rating.BusFactor },
    { name: 'Responsive Maintainer', value: rating.ResponsiveMaintainer },
    { name: 'License Score', value: rating.LicenseScore },
  ]

  return (
    <Box p={6} shadow="md" borderWidth="1px" borderRadius="lg" bg="white">
      <Heading as="h3" size="md" mb={4}>
        Package Metrics
      </Heading>
      <VStack spacing={4} align="stretch">
        {metrics.map((metric) => (
          <Box key={metric.name}>
            <Text fontWeight="semibold" mb={1}>
              {metric.name}: {metric.value.toFixed(2)}
            </Text>
            <Progress
              value={metric.value * 100}
              colorScheme={metric.value > 0.7 ? 'green' : metric.value > 0.4 ? 'yellow' : 'red'}
              aria-label={`${metric.name} score`}
            />
          </Box>
        ))}
      </VStack>
    </Box>
  )
}

