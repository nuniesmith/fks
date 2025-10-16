// Central dayjs instance & plugins
import dayjs from 'dayjs'
import utc from 'dayjs/plugin/utc'
import timezone from 'dayjs/plugin/timezone'
import relativeTime from 'dayjs/plugin/relativeTime'

// Add more plugins as needed (duration, advancedFormat, etc.)

dayjs.extend(utc)
dayjs.extend(timezone)
dayjs.extend(relativeTime)

export { dayjs }
export type Dayjs = dayjs.Dayjs
