function finiteCoordinate(value) {
  const coordinate = Number(value)
  return Number.isFinite(coordinate) ? coordinate : null
}

export function coordinateToRatio(clientX, rect) {
  const coordinate = finiteCoordinate(clientX)
  const left = finiteCoordinate(rect && rect.left)
  const width = finiteCoordinate(rect && rect.width)
  if (coordinate === null || left === null || width === null || width <= 0) return null
  return Math.min(1, Math.max(0, (coordinate - left) / width))
}

export function seekRatioFromEvent(event, rect) {
  const touch = (event && event.touches && event.touches[0])
    || (event && event.changedTouches && event.changedTouches[0])
  const coordinate = touch
    ? (touch.clientX ?? touch.pageX ?? touch.x)
    : (event && event.detail ? event.detail.x : event && event.clientX)
  return coordinateToRatio(coordinate, rect)
}
