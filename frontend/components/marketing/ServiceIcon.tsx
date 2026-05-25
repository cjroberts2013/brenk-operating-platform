/**
 * Maps editor-supplied icon names to actual Heroicon components.
 *
 * The editor stores a free-text icon name on each service row.
 * This renderer is forgiving — unknown names just don't render an
 * icon, which is fine (some services genuinely don't need one).
 *
 * To add a new mapping, drop the Heroicon import here and add a
 * case to the switch. No backend change needed; the editor can
 * type the new name as soon as it lands.
 */

import {
  BoltIcon,
  BuildingOffice2Icon,
  ClipboardDocumentCheckIcon,
  FireIcon,
  HomeIcon,
  HomeModernIcon,
  LightBulbIcon,
  PaintBrushIcon,
  Square3Stack3DIcon,
  SunIcon,
  TruckIcon,
  WrenchScrewdriverIcon,
} from '@heroicons/react/24/outline'

type IconComponent = React.ComponentType<React.SVGProps<SVGSVGElement>>

const ICON_MAP: Record<string, IconComponent> = {
  bolt: BoltIcon,
  building: BuildingOffice2Icon,
  checklist: ClipboardDocumentCheckIcon,
  fire: FireIcon,
  home: HomeIcon,
  'home-modern': HomeModernIcon,
  lightbulb: LightBulbIcon,
  paintbrush: PaintBrushIcon,
  stack: Square3Stack3DIcon,
  sun: SunIcon,
  truck: TruckIcon,
  wrench: WrenchScrewdriverIcon,
  'wrench-screwdriver': WrenchScrewdriverIcon,
}

export function ServiceIcon({
  name,
  className = 'size-6',
}: {
  name: string | null
  className?: string
}) {
  if (!name) return null
  const Component = ICON_MAP[name.toLowerCase()]
  if (!Component) return null
  return <Component className={className} aria-hidden="true" />
}
