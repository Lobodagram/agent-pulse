import AppKit
import SwiftUI

enum PulseBrand {
    static let logo = Bundle.main.url(forResource: "logo-128", withExtension: "png")
        .flatMap { NSImage(contentsOf: $0) }
}

struct PulseBrandMark: View {
    var size: CGFloat = 22
    var body: some View {
        if let image = PulseBrand.logo {
            Image(nsImage: image).resizable().scaledToFit()
                .frame(width: size, height: size).accessibilityHidden(true)
        }
    }
}
