import { StorefrontEditor } from '@/components/storefront/StorefrontEditor'
import { getStorefrontAdmin } from '@/lib/api/storefront'

export default async function StorefrontEditorPage() {
  const content = await getStorefrontAdmin()
  return <StorefrontEditor initial={content} />
}
