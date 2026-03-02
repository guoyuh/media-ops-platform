import axios from 'axios'

const http = axios.create({
  baseURL: `http://${window.location.hostname}:8000`,
  timeout: 120000,
})

export default http
