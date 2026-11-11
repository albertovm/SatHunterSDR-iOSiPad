@preconcurrency import CoreLocation
import Foundation
final class LocationProvider: NSObject, ObservableObject, CLLocationManagerDelegate {
    @Published private(set) var authorization: CLAuthorizationStatus = .notDetermined
    @Published private(set) var lastLocation: CLLocation?
    private let manager = CLLocationManager()
    var onLocation: ((CLLocation) -> Void)?
    override init() { super.init(); manager.delegate = self; manager.desiredAccuracy = kCLLocationAccuracyBest; manager.distanceFilter = 10; authorization = manager.authorizationStatus }
    func request() { manager.requestWhenInUseAuthorization() }
    func start() { manager.startUpdatingLocation() }
    func stop() { manager.stopUpdatingLocation() }
    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) { authorization = manager.authorizationStatus; if authorization == .authorizedAlways || authorization == .authorizedWhenInUse { manager.startUpdatingLocation() } }
    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) { guard let location = locations.last else { return }; lastLocation = location; onLocation?(location) }
}
