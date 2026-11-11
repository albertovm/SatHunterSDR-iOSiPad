@preconcurrency import CoreLocation
import Foundation
final class LocationProvider: NSObject, CLLocationManagerDelegate {
    private let manager = CLLocationManager()
    var onLocation: ((CLLocation) -> Void)?
    var onHeading: ((CLHeading) -> Void)?
    override init() { super.init(); manager.delegate = self; manager.desiredAccuracy = kCLLocationAccuracyBest; manager.distanceFilter = 10 }
    func request() { manager.requestWhenInUseAuthorization() }
    func start() { manager.startUpdatingLocation(); if CLLocationManager.headingAvailable() { manager.startUpdatingHeading() } }
    func stop() { manager.stopUpdatingLocation(); manager.stopUpdatingHeading() }
    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) { if manager.authorizationStatus == .authorizedAlways || manager.authorizationStatus == .authorizedWhenInUse { manager.startUpdatingLocation() } }
    func locationManager(_ manager: CLLocationManager, didUpdateHeading newHeading: CLHeading) { onHeading?(newHeading) }
    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) { if let location = locations.last { onLocation?(location) } }
}
