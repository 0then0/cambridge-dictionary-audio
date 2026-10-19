import XCTest

final class NavigationTests: XCTestCase {
  func testNativeNavigationSettingsAndSearchInput() {
    let app = XCUIApplication()
    app.launch()
    XCTAssertTrue(app.textFields["searchInput"].waitForExistence(timeout: 10))
    app.tabBars.buttons["Settings"].tap()
    XCTAssertTrue(app.navigationBars["Settings"].exists)
    app.tabBars.buttons["Collection"].tap()
    XCTAssertTrue(app.navigationBars["Collection"].exists)
    app.tabBars.buttons["Search"].tap()
    let input = app.textFields["searchInput"]
    input.tap()
    input.typeText("bank")
    XCTAssertTrue(app.buttons["findButton"].isEnabled)
  }
}
