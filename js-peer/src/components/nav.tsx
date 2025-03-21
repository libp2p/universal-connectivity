import { Fragment } from 'react'
import { Disclosure, DisclosureButton, DisclosurePanel, Menu, Transition } from '@headlessui/react'
import { Bars3Icon, BellIcon, XMarkIcon } from '@heroicons/react/24/outline'
import Link from 'next/link'
import Image from 'next/image'
import { useRouter } from 'next/router'

const navigationItems = [{ name: 'Source', href: 'https://github.com/libp2p/universal-connectivity' }]

function classNames(...classes: string[]) {
  return classes.filter(Boolean).join(' ')
}

export default function Navigation({ connectionInfoButton }: { connectionInfoButton?: React.ReactNode }) {
  const router = useRouter()

  return (
    <Disclosure as="nav" className="border-b border-gray-200 bg-white">
      {({ open }) => (
        <>
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="flex h-16 justify-between items-center">
              <div className="flex items-center">
                <div className="flex flex-shrink-0 items-center">
                  <Image src="/libp2p-logo.svg" alt="libp2p logo" height="46" width="46" />
                  <div className="ml-3 flex items-center">
                    <h1 className="text-xl font-semibold text-gray-900 hidden sm:block">Universal Connectivity</h1>
                    <Image
                      src="/libp2p-hero.svg"
                      alt="libp2p hero"
                      height="24"
                      width="24"
                      className="ml-2 hidden sm:block"
                    />
                  </div>
                </div>
              </div>

              <div className="flex items-center space-x-4">
                <div className="flex space-x-4">
                  {navigationItems.map((item) => (
                    <Link key={item.href} href={item.href} legacyBehavior>
                      <a
                        key={item.href}
                        className={classNames(
                          router.pathname === item.href
                            ? 'border-indigo-500 text-gray-900'
                            : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700',
                          'inline-flex items-center px-1 pt-1 text-sm font-medium',
                        )}
                        aria-current={router.pathname === item.href ? 'page' : undefined}
                      >
                        {item.name}
                      </a>
                    </Link>
                  ))}
                </div>
                <div className="flex items-center">{connectionInfoButton}</div>
              </div>
            </div>
          </div>
        </>
      )}
    </Disclosure>
  )
}
